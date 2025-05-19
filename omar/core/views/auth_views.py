from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.contrib import messages

from core.models import UserProfile, Company
from core.forms import LoginForm, SignUpForm
from core.decorators import approved_required

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            company_code = form.cleaned_data['company_code'].strip()
            user = authenticate(request, username=username, password=password)
            if user is not None:
                try:
                    company = Company.objects.get(code__iexact=company_code)
                except ObjectDoesNotExist:
                    messages.error(request, 'Invalid company code.')
                    return render(request, 'registration/login.html', {'form': form})

                if company.is_paused:
                    messages.error(request, 'This company is currently paused. Please contact the administrator.')
                    return render(request, 'registration/login.html', {'form': form})

                if user.is_superuser:
                    login(request, user)
                    request.session['company_id'] = company.id
                    messages.success(request, 'Logged in successfully as superuser.')
                    return redirect('dashboard')

                try:
                    user_profile = user.userprofile
                except ObjectDoesNotExist:
                    messages.error(request, 'User profile not found. Please contact the administrator.')
                    return render(request, 'registration/login.html', {'form': form})

                if user_profile.is_approved:
                    expected_company = user_profile.company
                    if expected_company and expected_company.code.lower() != company_code.lower():
                        messages.error(request, 'You are not authorized to log in with this company code.')
                        return render(request, 'registration/login.html', {'form': form})
                    login(request, user)
                    request.session['company_id'] = company.id
                    messages.success(request, 'Logged in successfully.')
                    return redirect('dashboard')
                else:
                    messages.error(request, 'Your account is awaiting admin approval.')
                    return render(request, 'registration/login.html', {'form': form})
            else:
                messages.error(request, 'Invalid username or password.')
                return render(request, 'registration/login.html', {'form': form})
        else:
            messages.error(request, 'Please correct the errors below.')
            return render(request, 'registration/login.html', {'form': form})
    else:
        form = LoginForm()
    return render(request, 'registration/login.html', {'form': form})

def logout_view(request):
    logout(request)
    messages.success(request, 'Logged out successfully.')
    return redirect('login')

@approved_required
def signup(request):
    if not request.user.userprofile.is_superuser_profile:
        messages.error(request, 'You do not have permission to create new users.')
        return redirect('dashboard')

    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = True
            user.save()
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.is_approved = True
            profile.company = request.user.userprofile.company
            profile.save()
            messages.success(request, 'User successfully created.')
            return redirect('dashboard')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = SignUpForm()
    return render(request, 'registration/signup.html', {'form': form})

@approved_required
def manage_users(request):
    if not request.user.userprofile.is_superuser_profile and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to manage users.')
        return redirect('dashboard')

    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('dashboard')

    try:
        company = Company.objects.get(id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company not found.')
        return redirect('dashboard')

    users = UserProfile.objects.all() if request.user.is_superuser else UserProfile.objects.filter(company=company)

    if request.method == 'POST' and 'delete_user' in request.POST:
        user_id = request.POST.get('user_id')
        user_to_delete = get_object_or_404(User, id=user_id)
        if user_to_delete != request.user and not user_to_delete.is_superuser:
            user_to_delete.delete()
            messages.success(request, 'User deleted successfully.')
        else:
            messages.error(request, 'Cannot delete your own account or a superuser.')
        return redirect('manage_users')

    return render(request, 'manage_users.html', {
        'users': users,
        'company': company,
        'current_user': request.user
    })
