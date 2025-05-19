from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib import messages
from django.db.models import Q
from django.db import IntegrityError
import re

from core.models import CompanyInfo, Company, SavedCarrier, CarrierFile
from core.decorators import approved_required

@approved_required
def saved_carriers(request):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('dashboard')

    try:
        company = Company.objects.get(id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company not found.')
        return redirect('dashboard')

    carriers = SavedCarrier.objects.filter(company_id=company_id, is_onboarded=False).order_by('-saved_at')
    return render(request, 'saved_carriers.html', {
        'company_info': company_info,
        'company': company,
        'carriers': carriers
    })

@approved_required
def save_carrier(request):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('dashboard')

    try:
        company = Company.objects.get(id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company not found.')
        return redirect('dashboard')

    if request.method == 'POST':
        # Extract form data
        legal_name = request.POST.get('legal_name', '').strip()
        mc_number = request.POST.get('mc_number', '').strip()
        dot_number = request.POST.get('dot_number', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        ein_number = request.POST.get('ein_number', '').strip()
        company_officer = request.POST.get('company_officer', '').strip()
        street = request.POST.get('street', '').strip()
        city = request.POST.get('city', '').strip()
        state = request.POST.get('state', '').strip()
        zip_code = request.POST.get('zip_code', '').strip()
        contact_person = request.POST.get('contact_person', '').strip()
        status = request.POST.get('status', 'Active').strip()

        # Validate required fields
        errors = []
        if not legal_name:
            errors.append('Legal Name is required.')
        if not mc_number:
            errors.append('MC Number is required.')
        if not dot_number:
            errors.append('DOT Number is required.')
        if state and not re.match(r'^[A-Z]{2}$', state):
            errors.append('State must be a 2-letter code (e.g., CA, NY).')
        if zip_code and not re.match(r'^\d{5}(-\d{4})?$', zip_code):
            errors.append('Zip Code must be 5 digits or 5+4 format (e.g., 12345 or 12345-6789).')

        if errors:
            for error in errors:
                messages.error(request, error)
            return render(request, 'save_carrier.html', {
                'company_info': company_info,
                'company': company,
                'form_data': request.POST,
            })

        try:
            # Check for duplicate MC or DOT numbers
            if SavedCarrier.objects.filter(company=company, mc_number=mc_number).exists():
                messages.error(request, f'A carrier with MC Number {mc_number} already exists.')
                return render(request, 'save_carrier.html', {
                    'company_info': company_info,
                    'company': company,
                    'form_data': request.POST,
                })
            if SavedCarrier.objects.filter(company=company, dot_number=dot_number).exists():
                messages.error(request, f'A carrier with DOT Number {dot_number} already exists.')
                return render(request, 'save_carrier.html', {
                    'company_info': company_info,
                    'company': company,
                    'form_data': request.POST,
                })

            carrier = SavedCarrier(
                company=company,
                legal_name=legal_name,
                mc_number=mc_number,
                dot_number=dot_number,
                email=email or None,
                phone=phone or None,
                ein_number=ein_number or None,
                company_officer=company_officer or None,
                street=street or None,
                city=city or None,
                state=state or None,
                zip_code=zip_code or None,
                contact_person=contact_person or None,
                created_by=request.user,
                status=status
            )
            carrier.save()
            messages.success(request, 'Carrier saved successfully.')
            return redirect('saved_carriers')
        except ValidationError as e:
            messages.error(request, f'Error saving carrier: {str(e)}')
            return render(request, 'save_carrier.html', {
                'company_info': company_info,
                'company': company,
                'form_data': request.POST,
            })
        except IntegrityError as e:
            messages.error(request, f'Database error: {str(e)}')
            return render(request, 'save_carrier.html', {
                'company_info': company_info,
                'company': company,
                'form_data': request.POST,
            })

    return render(request, 'save_carrier.html', {
        'company_info': company_info,
        'company': company,
    })

@approved_required
def onboarded_carriers(request):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('dashboard')

    try:
        company = Company.objects.get(id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company not found.')
        return redirect('dashboard')

    search_query = request.GET.get('search', '').strip()
    sort = request.GET.get('sort', 'saved_at')
    order = request.GET.get('order', 'desc')

    if sort not in ['legal_name', 'saved_at']:
        sort = 'saved_at'

    sort_field = f'-{sort}' if order == 'desc' else sort

    onboarded_carriers = SavedCarrier.objects.filter(company_id=company_id, is_onboarded=True)

    if search_query:
        onboarded_carriers = onboarded_carriers.filter(
            Q(legal_name__icontains=search_query) |
            Q(mc_number__icontains=search_query) |
            Q(dot_number__icontains=search_query)
        )

    onboarded_carriers = onboarded_carriers.order_by(sort_field)

    return render(request, 'onboarded_carriers.html', {
        'company_info': company_info,
        'company': company,
        'onboarded_carriers': onboarded_carriers,
        'search_query': search_query,
        'sort': sort,
        'order': order,
    })

@approved_required
def onboard_carrier(request, carrier_id):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('saved_carriers')

    try:
        company = Company.objects.get(id=company_id)
        carrier = get_object_or_404(SavedCarrier, id=carrier_id, company_id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Carrier not found.')
        return redirect('saved_carriers')

    if carrier.is_onboarded:
        messages.error(request, 'Carrier is already onboarded.')
        return redirect('saved_carriers')

    if request.method == 'POST':
        try:
            carrier.is_onboarded = True
            carrier.save()
            messages.success(request, 'Carrier onboarded successfully.')
            return redirect('onboarded_carriers')
        except ValidationError as e:
            messages.error(request, f'Error onboarding carrier: {str(e)}')

    return render(request, 'onboard_carrier.html', {
        'company_info': company_info,
        'company': company,
        'carrier': carrier,
    })

@approved_required
def delete_carrier(request, carrier_id):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('saved_carriers')

    try:
        company = Company.objects.get(id=company_id)
        carrier = get_object_or_404(SavedCarrier, id=carrier_id, company_id=company_id)
        carrier.delete()
        messages.success(request, 'Carrier deleted successfully.')
    except ObjectDoesNotExist:
        messages.error(request, 'Carrier not found.')

    next_page = request.GET.get('next', 'saved_carriers')
    return redirect(next_page)

@approved_required
def edit_carrier(request, carrier_id):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('saved_carriers')

    try:
        company = Company.objects.get(id=company_id)
        carrier = get_object_or_404(SavedCarrier, id=carrier_id, company_id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company or carrier not found.')
        return redirect('saved_carriers')

    if request.method == 'POST':
        try:
            # Validate required fields
            legal_name = request.POST.get('legal_name', '').strip()
            mc_number = request.POST.get('mc_number', '').strip()
            dot_number = request.POST.get('dot_number', '').strip()
            if not legal_name:
                messages.error(request, 'Legal Name is required.')
                return render(request, 'edit_carrier.html', {
                    'company_info': company_info,
                    'company': company,
                    'carrier': carrier,
                    'form_data': request.POST,
                })
            if not mc_number:
                messages.error(request, 'MC Number is required.')
                return render(request, 'edit_carrier.html', {
                    'company_info': company_info,
                    'company': company,
                    'carrier': carrier,
                    'form_data': request.POST,
                })
            if not dot_number:
                messages.error(request, 'DOT Number is required.')
                return render(request, 'edit_carrier.html', {
                    'company_info': company_info,
                    'company': company,
                    'carrier': carrier,
                    'form_data': request.POST,
                })

            carrier.legal_name = legal_name
            carrier.mc_number = mc_number
            carrier.dot_number = dot_number
            carrier.email = request.POST.get('email', carrier.email) or None
            carrier.phone = request.POST.get('phone', carrier.phone) or None
            carrier.street = request.POST.get('street', carrier.street) or None
            carrier.city = request.POST.get('city', carrier.city) or None
            carrier.state = request.POST.get('state', carrier.state) or None
            carrier.zip_code = request.POST.get('zip_code', carrier.zip_code) or None
            carrier.save()
            messages.success(request, 'Carrier updated successfully.')
            return redirect('saved_carriers')
        except ValidationError as e:
            messages.error(request, f'Error updating carrier: {str(e)}')
            return render(request, 'edit_carrier.html', {
                'company_info': company_info,
                'company': company,
                'carrier': carrier,
                'form_data': request.POST,
            })

    return render(request, 'edit_carrier.html', {
        'company_info': company_info,
        'company': company,
        'carrier': carrier
    })

@approved_required
def carrier_info(request, carrier_id):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('onboarded_carriers')

    try:
        company = Company.objects.get(id=company_id)
        carrier = get_object_or_404(SavedCarrier, id=carrier_id, company_id=company_id, is_onboarded=True)
    except ObjectDoesNotExist:
        messages.error(request, 'Carrier not found.')
        return redirect('onboarded_carriers')

    if request.method == 'POST':
        form_type = request.POST.get('form_type')

        if form_type == 'carrier_details':
            try:
                # Validate required fields
                legal_name = request.POST.get('legal_name', '').strip()
                mc_number = request.POST.get('mc_number', '').strip()
                dot_number = request.POST.get('dot_number', '').strip()
                if not legal_name:
                    messages.error(request, 'Legal Name is required.')
                    return render(request, 'carrier_info.html', {
                        'company_info': company_info,
                        'company': company,
                        'carrier': carrier,
                        'form_data': request.POST,
                    })
                if not mc_number:
                    messages.error(request, 'MC Number is required.')
                    return render(request, 'carrier_info.html', {
                        'company_info': company_info,
                        'company': company,
                        'carrier': carrier,
                        'form_data': request.POST,
                    })
                if not dot_number:
                    messages.error(request, 'DOT Number is required.')
                    return render(request, 'carrier_info.html', {
                        'company_info': company_info,
                        'company': company,
                        'carrier': carrier,
                        'form_data': request.POST,
                    })

                carrier.legal_name = legal_name
                carrier.mc_number = mc_number
                carrier.dot_number = dot_number
                carrier.email = request.POST.get('email', carrier.email) or None
                carrier.phone = request.POST.get('phone', carrier.phone) or None
                carrier.ein_number = request.POST.get('ein_number', carrier.ein_number) or None
                carrier.company_officer = request.POST.get('company_officer', carrier.company_officer) or None
                carrier.street = request.POST.get('street', carrier.street) or None
                carrier.city = request.POST.get('city', carrier.city) or None
                carrier.state = request.POST.get('state', carrier.state) or None
                carrier.zip_code = request.POST.get('zip_code', carrier.zip_code) or None
                carrier.contact_person = request.POST.get('contact_person', carrier.contact_person) or None
                carrier.status = request.POST.get('status', carrier.status)
                carrier.save()
                messages.success(request, 'Carrier details updated successfully.')
            except ValidationError as e:
                messages.error(request, f'Error updating carrier details: {str(e)}')

        elif form_type == 'file_upload':
            files = request.FILES.getlist('files')
            if files:
                for file in files:
                    CarrierFile.objects.create(carrier=carrier, file=file)
                messages.success(request, f'{len(files)} file(s) uploaded successfully.')
            else:
                messages.error(request, 'No files selected for upload.')

        elif form_type == 'delete_file':
            file_id = request.POST.get('file_id')
            try:
                file = CarrierFile.objects.get(id=file_id, carrier=carrier)
                file.delete()
                messages.success(request, 'File deleted successfully.')
            except CarrierFile.DoesNotExist:
                messages.error(request, 'File not found.')
        else:
            messages.error(request, 'Invalid form submission.')

        return redirect('carrier_info', carrier_id=carrier.id)

    return render(request, 'carrier_info.html', {
        'company_info': company_info,
        'company': company,
        'carrier': carrier,
    })
