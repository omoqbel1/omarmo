from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from .fmcsa import get_company_details
from .models import SavedCarrier, CompanyInfo
from .forms import CompanyInfoForm  # Assuming this form exists

@login_required
def dashboard(request):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    result = None
    if request.method == "POST" and "lookup" in request.POST:
        mc = request.POST.get("mc")
        dot = request.POST.get("dot")
        webkey = "ac1f4f4c53be930e69d0e4660e21499217cae894"
        result = get_company_details(mc, dot, webkey)

        if isinstance(result, dict):
            result = {
                k.replace(" ", "_")
                .replace("(", "")
                .replace(")", "")
                .replace("/", "_")
                .replace("#", "")
                .replace("-", "_"): v
                for k, v in result.items()
            }

    return render(request, 'dashboard.html', {"company_info": company_info, "result": result})

@login_required
def save_carrier(request):
    if request.method == 'POST':
        SavedCarrier.objects.create(
            user=request.user,
            dot_number=request.POST.get('dot'),
            mc_number=request.POST.get('mc'),
            legal_name=request.POST.get('legal_name'),
            email=request.POST.get('email'),
            phone=request.POST.get('phone')
        )
    return redirect('dashboard')

@login_required
def saved_carriers(request):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    carriers = SavedCarrier.objects.filter(user=request.user).order_by('-saved_at')
    return render(request, 'saved_carriers.html', {'company_info': company_info, 'carriers': carriers})

@login_required
def delete_carrier(request, carrier_id):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    carrier = get_object_or_404(SavedCarrier, id=carrier_id, user=request.user)
    carrier.delete()
    return redirect('saved_carriers')

@login_required
def edit_carrier(request, carrier_id):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    carrier = get_object_or_404(SavedCarrier, id=carrier_id, user=request.user)
    if request.method == 'POST':
        carrier.legal_name = request.POST.get('legal_name')
        carrier.email = request.POST.get('email')
        carrier.phone = request.POST.get('phone')
        carrier.save()
        return redirect('saved_carriers')
    return render(request, 'edit_carrier.html', {'company_info': company_info, 'carrier': carrier})

@login_required
def settings(request):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = CompanyInfoForm(request.POST, request.FILES, instance=company_info)
        if form.is_valid():
            form.save()
            return redirect('settings')  # Redirect to refresh the page with updated data
    else:
        form = CompanyInfoForm(instance=company_info)
    return render(request, 'settings.html', {'form': form, 'company_info': company_info})

def logout_view(request):
    logout(request)
    return redirect('dashboard')
