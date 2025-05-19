import logging
import json
import os
import sys
import subprocess
import tempfile
import threading
import time
from datetime import datetime

from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_protect
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.files.base import File
from django.db import transaction, DatabaseError, connection

from core.models import SavedCarrier, CarrierFile

# Set up logging
logger = logging.getLogger(__name__)

@csrf_protect
@login_required
@require_POST
def fetch_carrier_insurance(request):
    """
    View to handle the AJAX request for fetching carrier insurance information.
    Executes the FMCSA insurance scraper script and returns the results.
    """
    try:
        data = json.loads(request.body)
        mc_number = data.get('mc_number')
        if not mc_number:
            return JsonResponse({'error': 'MC number is required'}, status=400)

        logger.info(f"Insurance fetch requested for MC#: {mc_number} by user {request.user.username}")

        # Get the company_id from the user's profile - this is critical for multi-company setup
        company_id = None
        if hasattr(request.user, 'userprofile'):
            company_id = getattr(request.user.userprofile.company, 'id', None)
            logger.info(f"User {request.user.username} belongs to company ID: {company_id}")
        else:
            logger.warning(f"User {request.user.username} does not have a userprofile")

        # Find carrier by MC number AND company_id
        if company_id:
            carrier = SavedCarrier.objects.filter(
                mc_number=mc_number,
                company_id=company_id
            ).first()
            logger.info(f"Looking up carrier with MC# {mc_number} for company {company_id}, found carrier_id: {carrier.id if carrier else None}")
        else:
            # Fallback to MC number only if company_id is not available
            carrier = SavedCarrier.objects.filter(mc_number=mc_number).first()
            logger.info(f"Looking up carrier with MC# {mc_number} (no company filter), found carrier_id: {carrier.id if carrier else None}")

        if not carrier:
            logger.warning(f"Carrier with MC# {mc_number} not found")

        # Pass company_id to the thread
        thread = threading.Thread(
            target=run_insurance_scraper,
            args=(mc_number, request.user.id, carrier.id if carrier else None, company_id)
        )
        thread.daemon = True
        thread.start()
        result = execute_scraper_with_timeout(mc_number, timeout=15)
        if 'error' in result:
            logger.warning(f"Error in immediate scraper response: {result['error']}")
            return JsonResponse({
                'status': 'processing',
                'message': 'The insurance information is being processed in the background. Please check back later or refresh the page.',
                'insurance': [{
                    'type': 'Processing',
                    'policy_surety_number': 'Insurance data is being retrieved in the background.',
                    'posted_date': '',
                    'coverage_from': '',
                    'coverage_to': '',
                    'effective_date': '',
                    'cancellation_date': ''
                }],
                'insurance_carrier': 'Processing'
            })
        if carrier:
            # Make sure to pass company_id here too
            save_thread = threading.Thread(
                target=save_insurance_data,
                args=(carrier, result, request.user, company_id)  # Added company_id
            )
            save_thread.daemon = True
            save_thread.start()
        return JsonResponse({
            'status': 'success',
            'message': 'Insurance data retrieved successfully',
            'insurance': result.get('insurance', []),
            'insurance_carrier': result.get('insurance_carrier', ''),
            'carrier_id': carrier.id if carrier else None
        })
    except Exception as e:
        logger.exception(f"Error fetching insurance: {str(e)}")
        return JsonResponse({'error': f"An error occurred: {str(e)}", 'status': 'error'}, status=500)

@csrf_protect
@login_required
@require_POST
def check_insurance_status(request):
    try:
        data = json.loads(request.body)
        mc_number = data.get('mc_number')
        if not mc_number:
            return JsonResponse({'error': 'MC number is required'}, status=400)

        # Get company_id from userprofile
        company_id = None
        if hasattr(request.user, 'userprofile'):
            company_id = getattr(request.user.userprofile.company, 'id', None)
            logger.info(f"User {request.user.username} belongs to company ID: {company_id}")

        # Filter by both MC number AND company_id if available
        if company_id:
            carrier = SavedCarrier.objects.filter(
                mc_number=mc_number,
                company_id=company_id
            ).first()
            logger.info(f"Checking insurance status for MC# {mc_number} in company {company_id}, found carrier_id: {carrier.id if carrier else None}")
        else:
            carrier = SavedCarrier.objects.filter(mc_number=mc_number).first()
            logger.info(f"Checking insurance status for MC# {mc_number} (no company filter), found carrier_id: {carrier.id if carrier else None}")

        if not carrier:
            return JsonResponse({'error': f"Carrier with MC# {mc_number} not found"}, status=404)

        if carrier.insurance_type:
            insurance_entry = {
                'type': carrier.insurance_type,
                'policy_surety_number': carrier.policy_number or '',
                'posted_date': carrier.posted_date.strftime('%m/%d/%Y') if carrier.posted_date else '',
                'coverage_from': carrier.coverage_from or '',
                'coverage_to': carrier.coverage_to or '',
                'effective_date': carrier.effective_date.strftime('%m/%d/%Y') if carrier.effective_date else '',
                'cancellation_date': carrier.cancellation_date.strftime('%m/%d/%Y') if carrier.cancellation_date else ''
            }
            logger.info(f"Returning SavedCarrier data for MC# {mc_number}: {json.dumps(insurance_entry, indent=2)}")
            return JsonResponse({
                'status': 'success',
                'message': 'Insurance data is available',
                'insurance': [insurance_entry],
                'insurance_carrier': carrier.insurance_carrier or 'Unknown',
                'carrier_id': carrier.id
            })

        recent_insurance_files = CarrierFile.objects.filter(
            carrier=carrier,
            file__contains='insurance'
        ).order_by('-uploaded_at')[:1]

        if recent_insurance_files.exists():
            insurance_file = recent_insurance_files.first()
            try:
                with open(insurance_file.file.path, 'r') as f:
                    insurance_data = json.load(f)
                logger.info(f"Returning CarrierFile data for MC# {mc_number}: {json.dumps(insurance_data, indent=2)}")
                return JsonResponse({
                    'status': 'success',
                    'message': 'Insurance data is available from file',
                    'insurance': insurance_data.get('insurance', []),
                    'insurance_carrier': insurance_data.get('insurance_carrier', 'Unknown'),
                    'carrier_id': carrier.id,
                    'file_id': insurance_file.id
                })
            except Exception as e:
                logger.error(f"Error reading insurance file for carrier {carrier.id}: {str(e)}")

        logger.info(f"No insurance data available for MC# {mc_number}, returning processing status")
        return JsonResponse({
            'status': 'processing',
            'message': 'Insurance data is still being processed',
            'insurance': [{
                'type': 'Processing',
                'policy_surety_number': 'Insurance data is being retrieved in the background.',
                'posted_date': '',
                'coverage_from': '',
                'coverage_to': '',
                'effective_date': '',
                'cancellation_date': ''
            }],
            'insurance_carrier': 'Processing'
        })

    except Exception as e:
        logger.exception(f"Error checking insurance status: {str(e)}")
        return JsonResponse({'error': f"An error occurred: {str(e)}", 'status': 'error'}, status=500)

def test_endpoint(request):
    """
    Simple test endpoint to verify URL routing
    """
    return JsonResponse({'message': 'Test endpoint is working!'})

def execute_scraper_with_timeout(mc_number, timeout=15):
    """
    Execute the insurance scraper script with a timeout.
    Returns the result or an error if the timeout is reached.
    """
    try:
        script_path = getattr(settings, 'FMCSA_SCRAPER', {}).get(
            'SCRIPT_PATH',
            os.path.join(settings.BASE_DIR, 'scripts', 'fmcsa_insurance_scraper.py')
        )
        if not os.path.exists(script_path):
            logger.error(f"Scraper script not found at {script_path}")
            return {'error': f"Scraper script not found at {script_path}"}

        with tempfile.NamedTemporaryFile(mode='w+', delete=False, encoding='utf-8') as output_file:
            process = subprocess.Popen(
                [sys.executable, script_path, mc_number],
                stdout=output_file,
                stderr=output_file,
                text=True
            )
            start_time = time.time()
            while process.poll() is None and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                return {
                    'error': 'The request timed out. Insurance data is being processed in the background.'
                }

            output_file.flush()
            output_file.close()
            with open(output_file.name, 'r', encoding='utf-8') as f:
                output = f.read()

            try:
                os.unlink(output_file.name)
            except Exception as e:
                logger.warning(f"Failed to delete temporary file: {str(e)}")

        logger.info(f"Raw scraper output for MC# {mc_number}: {output[:1000]}...")
        try:
            insurance_data = json.loads(output)
            if isinstance(insurance_data, dict) and 'error' in insurance_data:
                return {'error': insurance_data['error'], 'insurance': []}
            logger.info(f"Parsed scraper output for MC# {mc_number}: {json.dumps(insurance_data, indent=2)}")
            return {
                'insurance': insurance_data,
                'insurance_carrier': insurance_data[0].get('insurance_carrier', 'Unknown') if insurance_data else ''
            }
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse scraper JSON output for MC# {mc_number}: {str(e)}")
            logger.debug(f"Raw output: {output[:1000]}...")
            return {'error': f"Invalid scraper output: {str(e)}", 'insurance': []}

    except Exception as e:
        logger.exception(f"Error executing scraper for MC# {mc_number}: {str(e)}")
        return {'error': f"Error executing scraper: {str(e)}"}

def run_insurance_scraper(mc_number, user_id=None, carrier_id=None, company_id=None):
    """
    Run the insurance scraper script in a background thread.
    This allows the web request to return quickly while the scraping continues.
    """
    try:
        logger.info(f"Starting background scraper for MC# {mc_number}, process {os.getpid()}, thread {threading.current_thread().name}")
        logger.info(f"Parameters: user_id={user_id}, carrier_id={carrier_id}, company_id={company_id}")

        # Rest of your existing code...

        if result.returncode == 0:
            try:
                insurance_data = json.loads(result.stdout)
                if isinstance(insurance_data, dict) and 'error' in insurance_data:
                    logger.error(f"Scraper returned error for MC# {mc_number}: {insurance_data['error']}")
                    return

                logger.info(f"Parsed insurance data: {insurance_data}")

                if user_id and carrier_id:
                    logger.info(f"Getting user with id {user_id}")
                    user = User.objects.get(id=user_id)

                    logger.info(f"Looking up carrier with id {carrier_id} and company_id {company_id}")

                    # Add these debug lines to examine the carriers in the database
                    carriers_with_id = list(SavedCarrier.objects.filter(id=carrier_id))
                    logger.info(f"Found {len(carriers_with_id)} carriers with id {carrier_id}")
                    for c in carriers_with_id:
                        logger.info(f"  Carrier {c.id} has company_id={getattr(c, 'company_id', None)}")

                    if company_id:
                        carriers_with_company = list(SavedCarrier.objects.filter(company_id=company_id))
                        logger.info(f"Found {len(carriers_with_company)} carriers in company {company_id}")

                        carriers_matching_both = list(SavedCarrier.objects.filter(id=carrier_id, company_id=company_id))
                        logger.info(f"Found {len(carriers_matching_both)} carriers matching both id={carrier_id} and company_id={company_id}")

                    # Use company_id when getting the carrier if provided
                    if company_id:
                        try:
                            carrier = SavedCarrier.objects.get(id=carrier_id, company_id=company_id)
                            logger.info(f"Found carrier {carrier.id} in company {carrier.company_id}")
                        except SavedCarrier.DoesNotExist:
                            logger.warning(f"Carrier with ID {carrier_id} and company_id {company_id} not found, trying without company filter")
                            carrier = SavedCarrier.objects.get(id=carrier_id)
                            logger.info(f"Found carrier {carrier.id} with company_id {getattr(carrier, 'company_id', None)}")
                    else:
                        carrier = SavedCarrier.objects.get(id=carrier_id)
                        logger.info(f"Found carrier {carrier.id} with company_id {getattr(carrier, 'company_id', None)}")

                    # FIXED: Pass company_id to save_insurance_data
                    save_insurance_data(carrier, {'insurance': insurance_data}, user, company_id)
                    logger.info(f"Saved insurance data for carrier {carrier_id} in company {getattr(carrier, 'company_id', None)}")

def run_insurance_scraper(mc_number, user_id=None, carrier_id=None, company_id=None):
    """
    Run the insurance scraper script in a background thread.
    This allows the web request to return quickly while the scraping continues.
    """
    try:
        logger.info(f"Starting background scraper for MC# {mc_number}, process {os.getpid()}, thread {threading.current_thread().name}")
        logger.info(f"Parameters: user_id={user_id}, carrier_id={carrier_id}, company_id={company_id}")

        script_path = getattr(settings, 'FMCSA_SCRAPER', {}).get(
            'SCRIPT_PATH',
            os.path.join(settings.BASE_DIR, 'scripts', 'fmcsa_insurance_scraper.py')
        )
        if not os.path.exists(script_path):
            logger.error(f"Scraper script not found at {script_path}")
            return

        cmd = [sys.executable, script_path, mc_number]
        logger.info(f"Executing command: {' '.join(cmd)}")
        start_time = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300
        )
        elapsed_time = time.time() - start_time
        logger.info(f"Scraper completed for MC# {mc_number}, return code: {result.returncode}, took {elapsed_time:.2f} seconds")
        logger.debug(f"Stdout: {result.stdout[:1000]}...")
        logger.debug(f"Stderr: {result.stderr}")

        if result.returncode == 0:
            try:
                insurance_data = json.loads(result.stdout)
                if isinstance(insurance_data, dict) and 'error' in insurance_data:
                    logger.error(f"Scraper returned error for MC# {mc_number}: {insurance_data['error']}")
                    return

                logger.info(f"Parsed insurance data: {insurance_data}")

                if user_id and carrier_id:
                    logger.info(f"Getting user with id {user_id}")
                    user = User.objects.get(id=user_id)

                    logger.info(f"Looking up carrier with id {carrier_id} and company_id {company_id}")

                    # Add these debug lines to examine the carriers in the database
                    carriers_with_id = list(SavedCarrier.objects.filter(id=carrier_id))
                    logger.info(f"Found {len(carriers_with_id)} carriers with id {carrier_id}")
                    for c in carriers_with_id:
                        logger.info(f"  Carrier {c.id} has company_id={getattr(c, 'company_id', None)}")

                    if company_id:
                        carriers_with_company = list(SavedCarrier.objects.filter(company_id=company_id))
                        logger.info(f"Found {len(carriers_with_company)} carriers in company {company_id}")

                        carriers_matching_both = list(SavedCarrier.objects.filter(id=carrier_id, company_id=company_id))
                        logger.info(f"Found {len(carriers_matching_both)} carriers matching both id={carrier_id} and company_id={company_id}")

                    # Use company_id when getting the carrier if provided
                    if company_id:
                        try:
                            carrier = SavedCarrier.objects.get(id=carrier_id, company_id=company_id)
                            logger.info(f"Found carrier {carrier.id} in company {carrier.company_id}")
                        except SavedCarrier.DoesNotExist:
                            logger.warning(f"Carrier with ID {carrier_id} and company_id {company_id} not found, trying without company filter")
                            carrier = SavedCarrier.objects.get(id=carrier_id)
                            logger.info(f"Found carrier {carrier.id} with company_id {getattr(carrier, 'company_id', None)}")
                    else:
                        carrier = SavedCarrier.objects.get(id=carrier_id)
                        logger.info(f"Found carrier {carrier.id} with company_id {getattr(carrier, 'company_id', None)}")

                    # FIXED: Pass company_id to save_insurance_data
                    save_insurance_data(carrier, {'insurance': insurance_data}, user, company_id)
                    logger.info(f"Saved insurance data for carrier {carrier_id} in company {getattr(carrier, 'company_id', None)}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse scraper JSON output for MC# {mc_number}: {str(e)}")
                logger.debug(f"Raw stdout: {result.stdout[:1000]}...")
                logger.debug(f"Full stdout saved to fmcsa_scraper_error.log")
                with open('fmcsa_scraper_error.log', 'w', encoding='utf-8') as f:
                    f.write(result.stdout)
            except Exception as e:
                logger.exception(f"Error processing insurance data for MC# {mc_number}: {str(e)}")
        else:
            logger.error(f"Scraper failed for MC# {mc_number}, return code: {result.returncode}, stderr: {result.stderr}")

    except subprocess.TimeoutExpired:
        logger.error(f"Scraper timed out for MC# {mc_number} after 300 seconds")
    except Exception as e:
        logger.exception(f"Error in background scraper for MC# {mc_number}: {str(e)}")
with open(__file__, 'r') as f:
    lines = f.readlines()
    for i, line in enumerate(lines):
        if 'try:' in line.strip():
            print(f"Try statement at line {i+1}: {line.strip()}")
