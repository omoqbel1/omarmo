from django.shortcuts import render, redirect
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib import messages

from core.models import CompanyInfo, Company, SavedCarrier
from core.fmcsa import get_company_details
from core.decorators import approved_required

@approved_required
def dashboard(request):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('login')

    try:
        company = Company.objects.get(id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company not found.')
        return redirect('login')

    result = None
    if request.method == "POST" and "lookup" in request.POST:
        mc = request.POST.get("mc", "").strip()
        dot = request.POST.get("dot", "").strip()
        if not mc and not dot:
            messages.error(request, 'Please provide either an MC# or DOT# for the lookup.')
        else:
            webkey = "ac1f4f4c53be930e69d0e4660e21499217cae894"  # Should move to env variable
            result = get_company_details(mc, dot, webkey)
            if isinstance(result, dict):
                result = {
                    k.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_").replace("#", "").replace("-", "_"): v
                    for k, v in result.items()
                }
            else:
                messages.error(request, 'Failed to retrieve company details.')

    monitored_carriers = None
    if request.user.userprofile.is_superuser_profile:
        monitored_carriers = SavedCarrier.objects.filter(company_id=company_id).order_by('-saved_at')

    return render(request, 'dashboard.html', {
        "company_info": company_info,
        "company": company,
        "result": result,
        "monitored_carriers": monitored_carriers
    })

@approved_required
def save_carrier(request):
    if request.method == 'POST':
        company_id = request.session.get('company_id')
        if not company_id:
            messages.error(request, 'Company ID not found in session.')
            return redirect('dashboard')

        try:
            company = Company.objects.get(id=company_id)
        except ObjectDoesNotExist:
            messages.error(request, 'Company not found.')
            return redirect('dashboard')

        mc_number = request.POST.get('mc', '').strip()
        if not mc_number:
            messages.error(request, 'MC# is required to save a carrier.')
            return redirect('dashboard')

        if SavedCarrier.objects.filter(company=company, mc_number=mc_number).exists():
            messages.error(request, f'A carrier with MC# {mc_number} already exists.')
            return redirect('dashboard')

        try:
            SavedCarrier.objects.create(
                company=company,
                dot_number=request.POST.get('dot', ''),
                mc_number=mc_number,
                legal_name=request.POST.get('legal_name', ''),
                email=request.POST.get('email', ''),
                phone=request.POST.get('phone', ''),
                ein_number=request.POST.get('ein_number', ''),
                company_officer=request.POST.get('company_officer', ''),
                address=request.POST.get('address', ''),
                contact_person=request.POST.get('contact_person', ''),
                created_by=request.user
            )
            messages.success(request, 'Carrier saved successfully.')
        except ValidationError as e:
            messages.error(request, f'Error saving carrier: {str(e)}')

    return redirect('dashboard')
