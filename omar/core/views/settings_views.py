from django.shortcuts import render, redirect
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages
from django.contrib.auth.models import User
from core.models import CompanyInfo, Company, UserProfile
from core.forms import CompanyInfoForm
from core.decorators import approved_required

@approved_required
def settings(request):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
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
        form = CompanyInfoForm(request.POST, request.FILES, instance=company_info)
        if form.is_valid():
            form.save()
            # Refresh company_info to reflect the updated logo
            company_info = CompanyInfo.objects.get(user=request.user)
            messages.success(request, 'Settings updated successfully.')
            # Re-instantiate form with updated instance
            form = CompanyInfoForm(instance=company_info)
            return render(request, 'settings.html', {
                'form': form,
                'company_info': company_info,
                'company': company
            })
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CompanyInfoForm(instance=company_info)

    return render(request, 'settings.html', {
        'form': form,
        'company_info': company_info,
        'company': company
    })

@approved_required
def delete_logo(request):
    if request.method == 'POST':
        company_info = CompanyInfo.objects.get(user=request.user)
        if company_info.logo:
            company_info.logo.delete(save=True)
            messages.success(request, 'Logo deleted successfully.')
        return redirect('settings')
    return redirect('settings')

@approved_required
def manage_users(request):
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

    # Only superusers or users with specific permissions can manage users
    if not request.user.is_superuser and not UserProfile.objects.get(user=request.user).is_superuser_profile:
        messages.error(request, 'You do not have permission to manage users.')
        return redirect('dashboard')

    user_profiles = UserProfile.objects.filter(company=company).select_related('user')

    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        action = request.POST.get('action')
        try:
            user_profile = UserProfile.objects.get(user_id=user_id, company=company)
            if action == 'approve':
                user_profile.is_approved = True
                user_profile.save()
                messages.success(request, f'User {user_profile.user.username} approved successfully.')
            elif action == 'disapprove':
                user_profile.is_approved = False
                user_profile.save()
                messages.success(request, f'User {user_profile.user.username} disapproved successfully.')
            elif action == 'make_superuser':
                user_profile.is_superuser_profile = True
                user_profile.save()
                messages.success(request, f'User {user_profile.user.username} set as superuser.')
            elif action == 'remove_superuser':
                user_profile.is_superuser_profile = False
                user_profile.save()
                messages.success(request, f'User {user_profile.user.username} removed as superuser.')
            elif action == 'delete':
                user_profile.user.delete()  # Deletes User and cascades to UserProfile
                messages.success(request, f'User {user_profile.user.username} deleted successfully.')
        except UserProfile.DoesNotExist:
            messages.error(request, 'User not found.')
        return redirect('manage_users')

    return render(request, 'manage_users.html', {
        'company_info': company_info,
        'company': company,
        'user_profiles': user_profiles,
    })
