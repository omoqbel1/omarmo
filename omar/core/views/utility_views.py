from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib import messages
from django.http import JsonResponse

from core.models import CompanyInfo, Company, CarrierFile, SavedCarrier
from core.decorators import approved_required
from core.fmcsa import get_company_details

@approved_required
def upload_carrier_file(request, carrier_id):
    try:
        company_id = request.session.get('company_id')
        if not company_id:
            messages.error(request, 'Company ID not found in session.')
            return redirect('onboarded_carriers')

        carrier = get_object_or_404(SavedCarrier, id=carrier_id, company_id=company_id)

        if request.method == 'POST':
            files = request.FILES.getlist('files')
            if files:
                for file in files:
                    CarrierFile.objects.create(carrier=carrier, file=file)
                messages.success(request, f'{len(files)} file(s) uploaded successfully.')
            else:
                messages.error(request, 'No files selected for upload.')
        return redirect('carrier_info', carrier_id=carrier.id)

    except Exception as e:
        messages.error(request, f'Error uploading file(s): {str(e)}')
        return redirect('carrier_info', carrier_id=carrier_id)

@approved_required
def delete_carrier_file(request, carrier_id, file_id):
    try:
        company_id = request.session.get('company_id')
        if not company_id:
            messages.error(request, 'Company ID not found in session.')
            return redirect('onboarded_carriers')

        carrier = get_object_or_404(SavedCarrier, id=carrier_id, company_id=company_id)
        file = get_object_or_404(CarrierFile, id=file_id, carrier=carrier)
        file.delete()
        messages.success(request, 'File deleted successfully.')
    except Exception as e:
        messages.error(request, f'Error deleting file: {str(e)}')
    return redirect('carrier_info', carrier_id=carrier_id)

@approved_required
def fmcsa_lookup(request):
    if request.method == 'POST':
        mc = request.POST.get('mc', '').strip()
        dot = request.POST.get('dot', '').strip()
        if not mc and not dot:
            return JsonResponse({'error': 'Provide MC or DOT number.'}, status=400)
        try:
            webkey = "ac1f4f4c53be930e69d0e4660e21499217cae894"
            result = get_company_details(mc, dot, webkey)
            if isinstance(result, dict):
                result = {
                    k.replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_").replace("#", "").replace("-", "_"): v
                    for k, v in result.items()
                }
                return JsonResponse({'data': result})
            else:
                return JsonResponse({'error': 'FMCSA lookup failed.'}, status=500)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method.'}, status=405)
