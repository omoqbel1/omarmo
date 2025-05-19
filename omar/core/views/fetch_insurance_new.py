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
    This version updates all carriers with the same MC number across all companies.
    """
    try:
        data = json.loads(request.body)
        mc_number = data.get('mc_number')
        if not mc_number:
            return JsonResponse({'error': 'MC number is required'}, status=400)

        logger.info(f"Insurance fetch requested for MC#: {mc_number} by user {request.user.username}")

        # Special handling for superusers
        is_superuser = request.user.is_superuser or (hasattr(request.user, 'userprofile') and getattr(request.user.userprofile, 'is_superuser_profile', False))
        logger.info(f"User {request.user.username} is_superuser: {is_superuser}")

        # Get the company context - for logging purposes
        company_id = None
        if hasattr(request.user, 'userprofile'):
            company_id = getattr(request.user.userprofile.company, 'id', None)
            logger.info(f"User {request.user.username} belongs to company ID: {company_id}")
        else:
            logger.warning(f"User {request.user.username} does not have a userprofile")

        # Find all carriers with this MC number across all companies
        all_carriers_with_mc = list(SavedCarrier.objects.filter(mc_number=mc_number).order_by('id'))

        if not all_carriers_with_mc:
            logger.warning(f"No carriers found with MC# {mc_number} in any company")
            return JsonResponse({'error': f"No carriers found with MC# {mc_number}"}, status=404)

        # Get the first carrier as our "reference" carrier
        reference_carrier = all_carriers_with_mc[0]
        logger.info(f"Using carrier ID {reference_carrier.id} in company {reference_carrier.company_id} as reference")

        # Log all carriers with this MC number
        logger.info(f"Found {len(all_carriers_with_mc)} carriers with MC# {mc_number} across all companies")
        for carrier in all_carriers_with_mc:
            logger.info(f"  Carrier ID {carrier.id} in company {carrier.company_id}")

        # Pass the scraping task to a background thread
        thread = threading.Thread(
            target=run_insurance_scraper_for_all,
            args=(mc_number, request.user.id, [c.id for c in all_carriers_with_mc])
        )
        thread.daemon = True
        thread.start()

        # Get immediate response from scraper
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

        # Start a thread to save the insurance data to ALL carriers with this MC number
        save_thread = threading.Thread(
            target=save_insurance_data_to_all_carriers,
            args=(all_carriers_with_mc, result, request.user)
        )
        save_thread.daemon = True
        save_thread.start()

        return JsonResponse({
            'status': 'success',
            'message': f'Insurance data retrieved successfully and will be applied to all {len(all_carriers_with_mc)} carriers with this MC number',
            'insurance': result.get('insurance', []),
            'insurance_carrier': result.get('insurance_carrier', ''),
            'carrier_id': reference_carrier.id,
            'company_id': reference_carrier.company_id,
            'carrier_count': len(all_carriers_with_mc)
        })
    except Exception as e:
        logger.exception(f"Error fetching insurance: {str(e)}")
        return JsonResponse({'error': f"An error occurred: {str(e)}", 'status': 'error'}, status=500)

@csrf_protect
@login_required
@require_POST
def check_insurance_status(request):
    """
    Endpoint to check if insurance data is available for a carrier.
    Returns the latest insurance data if available.
    """
    try:
        data = json.loads(request.body)
        mc_number = data.get('mc_number')
        if not mc_number:
            return JsonResponse({'error': 'MC number is required'}, status=400)

        # Special handling for superusers
        is_superuser = request.user.is_superuser or (hasattr(request.user, 'userprofile') and getattr(request.user.userprofile, 'is_superuser_profile', False))
        logger.info(f"User {request.user.username} is_superuser: {is_superuser}")

        # Get the company context
        company_id = None
        selected_company_id = data.get('company_id')  # Allow passing company_id from the frontend

        if hasattr(request.user, 'userprofile'):
            if selected_company_id:
                # Use explicitly selected company
                company_id = selected_company_id
                logger.info(f"Using selected company ID: {company_id}")
            else:
                # Use user's company
                company_id = getattr(request.user.userprofile.company, 'id', None)
                logger.info(f"User {request.user.username} belongs to company ID: {company_id}")
        else:
            logger.warning(f"User {request.user.username} does not have a userprofile")

        # First try to find carrier in the specific company context
        carrier = None
        if company_id:
            carrier = SavedCarrier.objects.filter(
                mc_number=mc_number,
                company_id=company_id
            ).first()
            logger.info(f"Looking up carrier with MC# {mc_number} for company {company_id}, found carrier_id: {carrier.id if carrier else None}")

        # If not found in current company, check for carrier in other companies
        if not carrier:
            existing_carrier = None
            if is_superuser:
                # Superusers can see carriers from all companies
                existing_carrier = SavedCarrier.objects.filter(mc_number=mc_number).first()
                logger.info(f"Superuser found carrier with MC# {mc_number} in another company: {existing_carrier.id if existing_carrier else None}")
            else:
                # Regular users only see carriers from other companies to know they exist
                existing_carrier = SavedCarrier.objects.filter(mc_number=mc_number).exclude(company_id=company_id).first()

            if existing_carrier:
                # Return a special status indicating the carrier exists but not in this company
                return JsonResponse({
                    'status': 'not_in_company',
                    'message': 'Carrier exists in another company. Creating a copy in your company.',
                    'mc_number': mc_number,
                    'dot_number': existing_carrier.dot_number,
                    'legal_name': existing_carrier.legal_name,
                    'from_company_id': existing_carrier.company_id
                })
            else:
                # No carrier found with this MC number in any company
                return JsonResponse({'error': f"Carrier with MC# {mc_number} not found"}, status=404)

        # Regular processing for found carrier
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

def run_insurance_scraper_for_all(mc_number, user_id=None, carrier_ids=None):
    """
    Run the insurance scraper script in a background thread.
    This version will update all carriers with the same MC number.
    """
    try:
        logger.info(f"Starting background scraper for MC# {mc_number}, process {os.getpid()}, thread {threading.current_thread().name}")
        logger.info(f"Will update {len(carrier_ids) if carrier_ids else 0} carriers with this MC#")

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

                if user_id and carrier_ids:
                    user = User.objects.get(id=user_id)

                    # Update all carriers with this MC number
                    carriers = SavedCarrier.objects.filter(id__in=carrier_ids)
                    save_insurance_data_to_all_carriers(carriers, {'insurance': insurance_data}, user)
                    logger.info(f"Saved insurance data for {len(carriers)} carriers with MC# {mc_number}")
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

def save_insurance_data_to_all_carriers(carriers, insurance_data, user=None):
    """
    Save the insurance data to all carriers with the same MC number.
    Updates all carriers in a single transaction.
    """
    try:
        if 'error' in insurance_data or not insurance_data.get('insurance'):
            logger.warning(f"No valid insurance data to save: {insurance_data}")
            return

        insurance = insurance_data['insurance'][0]
        logger.info(f"Updating insurance data on {len(carriers)} carriers: {json.dumps(insurance, indent=2)}")

        # First save it as a file for history
        for carrier in carriers:
            # Save new CarrierFile for history
            try:
                insurance_json = json.dumps(insurance_data)
                temp_filename = f"insurance_{carrier.mc_number}_{int(time.time())}.json"
                temp_path = os.path.join(tempfile.gettempdir(), temp_filename)

                with open(temp_path, 'w', encoding='utf-8') as f:
                    f.write(insurance_json)

                with open(temp_path, 'rb') as f:
                    file_obj = File(f)
                    carrier_file = CarrierFile(carrier=carrier)
                    carrier_file.file.save(f"insurance_{carrier.mc_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json", file_obj)

                try:
                    os.unlink(temp_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temporary file: {str(e)}")

                logger.info(f"Saved insurance data file for carrier {carrier.id} in company {carrier.company_id}")
            except Exception as e:
                logger.error(f"Error saving insurance file for carrier {carrier.id}: {str(e)}")

        # Extract the insurance values
        insurance_type = insurance.get('type', '') if insurance.get('type') != "No Insurance on file" else ''
        insurance_carrier_name = insurance.get('insurance_carrier', 'Unknown') if insurance.get('insurance_carrier') != "No Insurance on file" else ''
        policy_number = insurance.get('policy_surety_number', '') if insurance.get('policy_surety_number') != "No Insurance on file" else ''
        coverage_from = insurance.get('coverage_from', '') if insurance.get('coverage_from') != "No Insurance on file" else ''
        coverage_to = insurance.get('coverage_to', '') if insurance.get('coverage_to') != "No Insurance on file" else ''

        # Parse dates
        posted_date = None
        effective_date = None
        cancellation_date = None

        for date_str, date_field in [
            (insurance.get('posted_date', ''), 'posted_date'),
            (insurance.get('effective_date', ''), 'effective_date'),
            (insurance.get('cancellation_date', ''), 'cancellation_date')
        ]:
            if date_str and date_str != "No Insurance on file":
                for fmt in ('%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y'):
                    try:
                        date_obj = datetime.strptime(date_str, fmt).date()
                        if date_field == 'posted_date':
                            posted_date = date_obj
                        elif date_field == 'effective_date':
                            effective_date = date_obj
                        elif date_field == 'cancellation_date':
                            cancellation_date = date_obj
                        break
                    except ValueError:
                        continue

        # Update all carriers in a single query
        update_fields = {}
        if insurance_type:
            update_fields['insurance_type'] = insurance_type
        if insurance_carrier_name:
            update_fields['insurance_carrier'] = insurance_carrier_name
        if policy_number:
            update_fields['policy_number'] = policy_number
        if coverage_from:
            update_fields['coverage_from'] = coverage_from
        if coverage_to:
            update_fields['coverage_to'] = coverage_to
        if posted_date:
            update_fields['posted_date'] = posted_date
        if effective_date:
            update_fields['effective_date'] = effective_date
        if cancellation_date:
            update_fields['cancellation_date'] = cancellation_date

        if update_fields:
            with transaction.atomic():
                # Update all carriers at once
                carrier_ids = [c.id for c in carriers]
                SavedCarrier.objects.filter(id__in=carrier_ids).update(**update_fields)
                logger.info(f"Updated insurance fields for {len(carriers)} carriers with MC# {carriers[0].mc_number if carriers else 'unknown'}")

            # Log the update for each carrier
            for carrier in carriers:
                logger.info(f"Updated insurance data for carrier {carrier.id} in company {carrier.company_id}")

    except Exception as e:
        logger.exception(f"Error saving insurance data to multiple carriers: {str(e)}")

# For backwards compatibility
def save_insurance_data(carrier, insurance_data, user=None, company_id=None):
    """
    Legacy method that redirects to the new centralized method.
    """
    # Find all carriers with the same MC number
    mc_number = carrier.mc_number
    all_carriers = SavedCarrier.objects.filter(mc_number=mc_number)

    # Use the new method to update all carriers
    save_insurance_data_to_all_carriers(all_carriers, insurance_data, user)

    return
