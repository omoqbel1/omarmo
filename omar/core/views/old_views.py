from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib import messages
from django.db.models import Q
from .fmcsa import get_company_details
from .models import SavedCarrier, CompanyInfo, UserProfile, Company, Customer, Load, CarrierFile, Commodity, AdditionalPickup, AdditionalDelivery
from .forms import CompanyInfoForm, SignUpForm, LoginForm

# Custom decorator for approved users
def approved_required(view_func):
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('login')
        if not request.user.is_superuser and (not hasattr(request.user, 'userprofile') or not request.user.userprofile.is_approved):
            return render(request, 'registration/approval_pending.html', {'message': 'Your account is awaiting admin approval.'})
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            company_code = form.cleaned_data['company_code'].strip()
            print(f"Attempting login with username: {username}, company_code: {company_code}")
            user = authenticate(request, username=username, password=password)
            if user is not None:
                print(f"User authenticated: {user.username}")
                try:
                    company = Company.objects.get(code__iexact=company_code)  # Case-insensitive lookup
                    print(f"Company found: {company.code}")
                except ObjectDoesNotExist:
                    print(f"Company with code '{company_code}' not found.")
                    messages.error(request, 'Invalid company code.')
                    return render(request, 'registration/login.html', {'form': form})

                if company.is_paused:
                    print(f"Company {company.code} is paused.")
                    messages.error(request, 'This company is currently paused. Please contact the administrator.')
                    return render(request, 'registration/login.html', {'form': form})

                if user.is_superuser:
                    print("User is superuser, allowing login with any company code.")
                    login(request, user)
                    request.session['company_id'] = company.id
                    messages.success(request, 'Logged in successfully as superuser.')
                    return redirect('dashboard')

                try:
                    user_profile = user.userprofile
                    print(f"UserProfile found: is_approved={user_profile.is_approved}, company={user_profile.company}")
                except ObjectDoesNotExist:
                    print("UserProfile does not exist for this user.")
                    messages.error(request, 'User profile not found. Please contact the administrator.')
                    return render(request, 'registration/login.html', {'form': form})

                if user_profile.is_approved:
                    expected_company = user_profile.company
                    # Compare company codes case-insensitively
                    if expected_company and expected_company.code.lower() != company_code.lower():
                        print(f"User not authorized for company code: expected {expected_company.code}, got {company_code}")
                        messages.error(request, 'You are not authorized to log in with this company code.')
                        return render(request, 'registration/login.html', {'form': form})
                    login(request, user)
                    request.session['company_id'] = company.id
                    messages.success(request, 'Logged in successfully.')
                    return redirect('dashboard')
                else:
                    print("User account not approved.")
                    messages.error(request, 'Your account is awaiting admin approval.')
                    return render(request, 'registration/login.html', {'form': form})
            else:
                print("Authentication failed: Invalid username or password.")
                messages.error(request, 'Invalid username or password.')
                return render(request, 'registration/login.html', {'form': form})
        else:
            print("Form validation failed:", form.errors.as_data())
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
            profile, created = UserProfile.objects.get_or_create(user=user)
            profile.is_approved = True
            profile.company = request.user.userprofile.company
            profile.save()
            messages.success(request, 'User successfully created.')
            return redirect('dashboard')
        else:
            print("Form errors:", form.errors.as_data())
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

    if request.user.is_superuser:
        users = UserProfile.objects.all()
    else:
        users = UserProfile.objects.filter(company=company)

    if request.method == 'POST':
        if 'delete_user' in request.POST:
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

@approved_required
def dashboard(request):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
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
        print("POST data:", request.POST)
        mc = request.POST.get("mc", "").strip()
        dot = request.POST.get("dot", "").strip()
        if not mc and not dot:
            messages.error(request, 'Please provide either an MC# or DOT# for the lookup.')
        else:
            webkey = "ac1f4f4c53be930e69d0e4660e21499217cae894"  # Consider moving to environment variable
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
        print("POST data:", request.POST)
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
            carrier = SavedCarrier.objects.create(
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
            print("Saved carrier:", carrier.__dict__)
            messages.success(request, 'Carrier saved successfully.')
            return redirect('dashboard')
        except ValidationError as e:
            print("Error saving carrier:", str(e))
            messages.error(request, f'Error saving carrier: {str(e)}')
            return redirect('dashboard')
    return redirect('dashboard')

@approved_required
def saved_carriers(request):
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

    carriers = SavedCarrier.objects.filter(company_id=company_id, is_onboarded=False).order_by('-saved_at')
    return render(request, 'saved_carriers.html', {
        'company_info': company_info,
        'company': company,
        'carriers': carriers
    })

@approved_required
def onboarded_carriers(request):
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
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
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
            print("Carrier onboarded:", carrier.__dict__)
            messages.success(request, 'Carrier onboarded successfully.')
            return redirect('onboarded_carriers')
        except ValidationError as e:
            print("Error onboarding carrier:", str(e))
            messages.error(request, f'Error onboarding carrier: {str(e)}')
            return redirect('saved_carriers')

    return render(request, 'onboard_carrier.html', {
        'company_info': company_info,
        'company': company,
        'carrier': carrier,
    })

@approved_required
def delete_carrier(request, carrier_id):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
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
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
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
        print("POST data:", request.POST)
        try:
            carrier.legal_name = request.POST.get('legal_name', carrier.legal_name)
            carrier.email = request.POST.get('email', carrier.email)
            carrier.phone = request.POST.get('phone', carrier.phone)
            carrier.save()
            print("Updated carrier:", carrier.__dict__)
            messages.success(request, 'Carrier updated successfully.')
            return redirect('saved_carriers')
        except ValidationError as e:
            print("Error updating carrier:", str(e))
            messages.error(request, f'Error updating carrier: {str(e)}')
            return render(request, 'edit_carrier.html', {
                'company_info': company_info,
                'company': company,
                'carrier': carrier
            })

    return render(request, 'edit_carrier.html', {
        'company_info': company_info,
        'company': company,
        'carrier': carrier
    })

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
        print("POST data:", request.POST)
        print("FILES data:", request.FILES)
        form = CompanyInfoForm(request.POST, request.FILES, instance=company_info)
        if form.is_valid():
            company_info = form.save()
            print("Saved CompanyInfo (settings):", company_info.__dict__)
            messages.success(request, 'Settings updated successfully.')
            return redirect('settings')
        else:
            print("Form errors:", form.errors.as_data())
            messages.error(request, 'Please correct the errors below.')
    else:
        form = CompanyInfoForm(instance=company_info)

    return render(request, 'settings.html', {
        'form': form,
        'company_info': company_info,
        'company': company
    })

@approved_required
def my_loads(request):
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

    sort = request.GET.get('sort', 'load_number')
    order = request.GET.get('order', 'asc')

    if sort not in ['load_number', 'status']:
        sort = 'load_number'

    sort_field = f'-{sort}' if order == 'desc' else sort

    loads = Load.objects.filter(company=company).order_by(sort_field)

    return render(request, 'my_loads.html', {
        'company_info': company_info,
        'company': company,
        'loads': loads,
        'sort': sort,
        'order': order,
    })

@approved_required
def my_customers(request):
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

    customers = Customer.objects.filter(company=company).order_by('customer_id')

    return render(request, 'my_customers.html', {
        'company_info': company_info,
        'company': company,
        'customers': customers
    })

@approved_required
def add_customer(request):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('my_customers')

    try:
        company = Company.objects.get(id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company not found.')
        return redirect('my_customers')

    if request.method == 'POST':
        print("POST data:", request.POST)
        try:
            last_customer = Customer.objects.filter(company=company).order_by('-customer_id').first()
            next_customer_number = last_customer.customer_id + 1 if last_customer else 1001

            customer = Customer.objects.create(
                company=company,
                customer_id=next_customer_number,
                company_name=request.POST.get('company_name', ''),
                name=request.POST.get('name', 'Unknown Customer'),
                address=request.POST.get('address', ''),
                city=request.POST.get('city', ''),
                state=request.POST.get('state', ''),
                zip=request.POST.get('zip', ''),
                phone=request.POST.get('phone', ''),
                email=request.POST.get('email', '')
            )
            print("Created customer:", customer.__dict__)
            messages.success(request, f'Customer {customer.name} added successfully.')
            return redirect('my_customers')
        except ValidationError as e:
            print("Error adding customer:", str(e))
            messages.error(request, f'Error adding customer: {str(e)}')
            return render(request, 'add_customer.html', {
                'company_info': company_info,
                'company': company
            })

    return render(request, 'add_customer.html', {
        'company_info': company_info,
        'company': company
    })

@approved_required
def edit_customer(request, customer_id):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('my_customers')

    try:
        company = Company.objects.get(id=company_id)
        customer = get_object_or_404(Customer, company=company, customer_id=customer_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company or customer not found.')
        return redirect('my_customers')

    if request.method == 'POST':
        print("POST data:", request.POST)
        try:
            customer.company_name = request.POST.get('company_name', customer.company_name)
            customer.name = request.POST.get('name', customer.name)
            if not customer.name:
                customer.name = 'Unknown Customer'
            customer.address = request.POST.get('address', customer.address)
            customer.city = request.POST.get('city', customer.city)
            customer.state = request.POST.get('state', customer.state)
            customer.zip = request.POST.get('zip', customer.zip)
            customer.phone = request.POST.get('phone', customer.phone)
            customer.email = request.POST.get('email', customer.email)
            customer.save()
            print("Updated customer:", customer.__dict__)
            messages.success(request, f'Customer {customer.name} updated successfully.')
            return redirect('my_customers')
        except ValidationError as e:
            print("Error updating customer:", str(e))
            messages.error(request, f'Error updating customer: {str(e)}')
            return render(request, 'edit_customer.html', {
                'company_info': company_info,
                'company': company,
                'customer': customer,
                'customer_id': customer_id
            })

    return render(request, 'edit_customer.html', {
        'company_info': company_info,
        'company': company,
        'customer': customer,
        'customer_id': customer_id
    })

@approved_required
def delete_customer(request, customer_id):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('my_customers')

    try:
        company = Company.objects.get(id=company_id)
        customer = get_object_or_404(Customer, company=company, customer_id=customer_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company or customer not found.')
        return redirect('my_customers')

    if request.method == 'POST':
        customer_name = customer.name
        customer.delete()
        messages.success(request, f'Customer {customer_name} deleted successfully.')
        return redirect('my_customers')

    return render(request, 'delete_customer.html', {
        'company_info': company_info,
        'company': company,
        'customer': customer,
        'customer_id': customer_id,
    })

@approved_required
def add_load(request):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('my_loads')

    try:
        company = Company.objects.get(id=company_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company not found.')
        return redirect('my_loads')

    customers = Customer.objects.filter(company=company).order_by('name')
    onboarded_carriers = SavedCarrier.objects.filter(company_id=company_id, is_onboarded=True).order_by('legal_name')

    if request.method == 'POST':
        print("POST data:", request.POST)
        customer_name = request.POST.get('customer_name', '').strip()

        if customer_name:
            customer_exists = Customer.objects.filter(company=company, name__iexact=customer_name).exists()
            if not customer_exists:
                messages.error(request, f'Customer "{customer_name}" does not exist. Please add the customer first.')
                return render(request, 'add_load.html', {
                    'company_info': company_info,
                    'company': company,
                    'customers': customers,
                    'onboarded_carriers': onboarded_carriers
                })
        else:
            messages.error(request, 'Please select a customer.')
            return render(request, 'add_load.html', {
                'company_info': company_info,
                'company': company,
                'customers': customers,
                'onboarded_carriers': onboarded_carriers
            })

        try:
            last_load = Load.objects.filter(company=company).order_by('-load_number').first()
            next_load_number = last_load.load_number + 1 if last_load else 1002

            pickup_date = request.POST.get('pickup_date') or None
            delivery_date = request.POST.get('delivery_date') or None
            pickup_appointment_time = request.POST.get('pickup_appointment_time') or None
            delivery_appointment_time = request.POST.get('delivery_appointment_time') or None

            cust_miles = int(request.POST.get('cust_miles', '0') or '0')
            carr_miles = int(request.POST.get('carr_miles', '0') or '0')
            cust_amt = float(request.POST.get('cust_amt', '0.00') or '0.00')
            carr_amt = float(request.POST.get('carr_amt', '0.00') or '0.00')

            carrier_id = request.POST.get('carrier')
            carrier = None
            if carrier_id:
                try:
                    carrier = SavedCarrier.objects.get(id=carrier_id, company_id=company_id, is_onboarded=True)
                    carrier_name = carrier.legal_name
                except SavedCarrier.DoesNotExist:
                    messages.error(request, 'Selected carrier is not onboarded or does not exist.')
                    return render(request, 'add_load.html', {
                        'company_info': company_info,
                        'company': company,
                        'customers': customers,
                        'onboarded_carriers': onboarded_carriers
                    })
            else:
                carrier_name = ''

            load_data = {
                'company': company,
                'load_number': next_load_number,
                'status': request.POST.get('status', 'ACTIVE'),
                'customer': customer_name,
                'carrier': carrier_name,
                'pickup_name': request.POST.get('pickup_name', ''),
                'pickup_date': pickup_date if pickup_date else None,
                'pickup_appointment_time': pickup_appointment_time if pickup_appointment_time else None,
                'pickup_city': request.POST.get('pickup_city', ''),
                'pickup_state': request.POST.get('pickup_state', ''),
                'pickup_zip': request.POST.get('pickup_zip', ''),
                'pickup_address': request.POST.get('pickup_address', ''),
                'pickup_phone': request.POST.get('pickup_phone', ''),
                'pickup_email': request.POST.get('pickup_email', ''),
                'pickup_instructions': request.POST.get('pickup_instructions', ''),
                'pickup_internal_notes': request.POST.get('pickup_internal_notes', ''),
                'delivery_name': request.POST.get('delivery_name', ''),
                'delivery_date': delivery_date if delivery_date else None,
                'delivery_appointment_time': delivery_appointment_time if delivery_appointment_time else None,
                'delivery_city': request.POST.get('delivery_city', ''),
                'delivery_state': request.POST.get('delivery_state', ''),
                'delivery_zip': request.POST.get('delivery_zip', ''),
                'delivery_address': request.POST.get('delivery_address', ''),
                'delivery_phone': request.POST.get('delivery_phone', ''),
                'delivery_email': request.POST.get('delivery_email', ''),
                'delivery_instructions': request.POST.get('delivery_instructions', ''),
                'cust_miles': cust_miles,
                'cust_rate': 0.00,
                'carr_miles': carr_miles,
                'carr_rate': 0.00,
                'cust_amt': cust_amt,
                'carr_amt': carr_amt,
                'total_miles': int(request.POST.get('total_miles', '0') or '0'),
                'total_amount': float(request.POST.get('total_amount', '0.00') or '0.00'),
                'driver_1': request.POST.get('driver_1', ''),
                'driver_1_cell': request.POST.get('driver_1_cell', ''),
                'driver_2': request.POST.get('driver_2', ''),
                'driver_2_cell': request.POST.get('driver_2_cell', ''),
                'truck_number': request.POST.get('truck_number', ''),
                'trailer_number': request.POST.get('trailer_number', ''),
            }

            if load_data['carrier'] and load_data['status'] == 'ACTIVE':
                load_data['status'] = 'BOOKED'

            load = Load.objects.create(**load_data)
            print("Created load:", load.__dict__)

            # Process commodities
            commodity_types = request.POST.getlist('commodity_type[]')
            commodity_descriptions = request.POST.getlist('commodity_description[]')
            commodity_quantities = request.POST.getlist('commodity_qty[]')
            commodity_weights = request.POST.getlist('commodity_weight[]')
            commodity_values = request.POST.getlist('commodity_value[]')

            for type, desc, qty, weight, value in zip(commodity_types, commodity_descriptions, commodity_quantities, commodity_weights, commodity_values):
                if desc and qty:  # Ensure required fields are not empty (type is optional)
                    try:
                        commodity = Commodity.objects.create(
                            load=load,
                            type=type if type else '',
                            description=desc,
                            quantity=int(qty),
                            weight=float(weight) if weight else 0.0,
                            value=float(value) if value else 0.00
                        )
                        print("Created commodity:", commodity.__dict__)
                    except ValueError as e:
                        print("Error creating commodity:", str(e))
                        messages.error(request, f'Invalid commodity data: {str(e)}')

            # Process additional pickups
            additional_pickup_names = request.POST.getlist('additional_pickup_name[]')
            additional_pickup_addresses = request.POST.getlist('additional_pickup_address[]')
            additional_pickup_cities = request.POST.getlist('additional_pickup_city[]')
            additional_pickup_states = request.POST.getlist('additional_pickup_state[]')
            additional_pickup_zips = request.POST.getlist('additional_pickup_zip[]')
            additional_pickup_dates = request.POST.getlist('additional_pickup_date[]')
            additional_pickup_phones = request.POST.getlist('additional_pickup_phone[]')
            additional_pickup_emails = request.POST.getlist('additional_pickup_email[]')
            additional_pickup_appointment_times = request.POST.getlist('additional_pickup_appointment_time[]')
            additional_pickup_instructions = request.POST.getlist('additional_pickup_instructions[]')

            for name, addr, city, state, zip_code, date, phone, email, time, instr in zip(
                additional_pickup_names, additional_pickup_addresses, additional_pickup_cities,
                additional_pickup_states, additional_pickup_zips, additional_pickup_dates,
                additional_pickup_phones, additional_pickup_emails, additional_pickup_appointment_times,
                additional_pickup_instructions
            ):
                if addr:  # Ensure address is not empty
                    pickup = AdditionalPickup.objects.create(
                        load=load,
                        name=name,
                        address=addr,
                        city=city,
                        state=state,
                        zip=zip_code,
                        date=date or None,
                        phone=phone,
                        email=email,
                        appointment_time=time,
                        instructions=instr
                    )
                    print("Created additional pickup:", pickup.__dict__)

            # Process additional deliveries
            additional_delivery_names = request.POST.getlist('additional_delivery_name[]')
            additional_delivery_addresses = request.POST.getlist('additional_delivery_address[]')
            additional_delivery_cities = request.POST.getlist('additional_delivery_city[]')
            additional_delivery_states = request.POST.getlist('additional_delivery_state[]')
            additional_delivery_zips = request.POST.getlist('additional_delivery_zip[]')
            additional_delivery_dates = request.POST.getlist('additional_delivery_date[]')
            additional_delivery_phones = request.POST.getlist('additional_delivery_phone[]')
            additional_delivery_emails = request.POST.getlist('additional_delivery_email[]')
            additional_delivery_appointment_times = request.POST.getlist('additional_delivery_appointment_time[]')
            additional_delivery_instructions = request.POST.getlist('additional_delivery_instructions[]')

            for name, addr, city, state, zip_code, date, phone, email, time, instr in zip(
                additional_delivery_names, additional_delivery_addresses, additional_delivery_cities,
                additional_delivery_states, additional_delivery_zips, additional_delivery_dates,
                additional_delivery_phones, additional_delivery_emails, additional_delivery_appointment_times,
                additional_delivery_instructions
            ):
                if addr:  # Ensure address is not empty
                    delivery = AdditionalDelivery.objects.create(
                        load=load,
                        name=name,
                        address=addr,
                        city=city,
                        state=state,
                        zip=zip_code,
                        date=date or None,
                        phone=phone,
                        email=email,
                        appointment_time=time,
                        instructions=instr
                    )
                    print("Created additional delivery:", delivery.__dict__)

            messages.success(request, f'Load #{load.load_number} added successfully.')
            return redirect('my_loads')

        except (ValueError, ValidationError) as e:
            print("Error adding load:", str(e))
            messages.error(request, f'Error adding load: {str(e)}')
            return render(request, 'add_load.html', {
                'company_info': company_info,
                'company': company,
                'customers': customers,
                'onboarded_carriers': onboarded_carriers
            })

    return render(request, 'add_load.html', {
        'company_info': company_info,
        'company': company,
        'customers': customers,
        'onboarded_carriers': onboarded_carriers
    })

@approved_required
def edit_load(request, load_id):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('my_loads')

    try:
        company = Company.objects.get(id=company_id)
        load = get_object_or_404(Load, company=company, load_number=load_id)
    except ObjectDoesNotExist:
        messages.error(request, 'Company or load not found.')
        return redirect('my_loads')

    customers = Customer.objects.filter(company=company).order_by('name')
    onboarded_carriers = SavedCarrier.objects.filter(company_id=company_id, is_onboarded=True).order_by('legal_name')

    if request.method == 'POST':
        print("POST data:", request.POST)
        customer_name = request.POST.get('customer_name', '').strip()

        if customer_name:
            customer_exists = Customer.objects.filter(company=company, name__iexact=customer_name).exists()
            if not customer_exists:
                messages.error(request, f'Customer "{customer_name}" does not exist. Please add the customer first.')
                return render(request, 'edit_load.html', {
                    'company_info': company_info,
                    'company': company,
                    'load': load,
                    'load_id': load_id,
                    'customers': customers,
                    'onboarded_carriers': onboarded_carriers
                })
        else:
            messages.error(request, 'Please select a customer.')
            return render(request, 'edit_load.html', {
                'company_info': company_info,
                'company': company,
                'load': load,
                'load_id': load_id,
                'customers': customers,
                'onboarded_carriers': onboarded_carriers
            })

        try:
            cust_miles = int(request.POST.get('cust_miles', load.cust_miles) or '0')
            carr_miles = int(request.POST.get('carr_miles', load.carr_miles) or '0')
            cust_amt = float(request.POST.get('cust_amt', load.cust_amt) or '0.00')
            carr_amt = float(request.POST.get('carr_amt', load.carr_amt) or '0.00')

            carrier_name = load.carrier
            if 'carrier' in request.POST and request.POST['carrier']:
                try:
                    carrier = SavedCarrier.objects.get(id=request.POST['carrier'], company_id=company_id, is_onboarded=True)
                    carrier_name = carrier.legal_name
                except SavedCarrier.DoesNotExist:
                    messages.error(request, 'Selected carrier is not onboarded or does not exist.')
                    return render(request, 'edit_load.html', {
                        'company_info': company_info,
                        'company': company,
                        'load': load,
                        'load_id': load_id,
                        'customers': customers,
                        'onboarded_carriers': onboarded_carriers
                    })

            # Update load fields
            load.status = request.POST.get('status', load.status)
            load.customer = customer_name
            load.carrier = carrier_name
            load.pickup_name = request.POST.get('pickup_name', load.pickup_name)
            load.pickup_date = request.POST.get('pickup_date') or load.pickup_date
            load.pickup_appointment_time = request.POST.get('pickup_appointment_time') or load.pickup_appointment_time
            load.pickup_city = request.POST.get('pickup_city', load.pickup_city)
            load.pickup_state = request.POST.get('pickup_state', load.pickup_state)
            load.pickup_zip = request.POST.get('pickup_zip', load.pickup_zip)
            load.pickup_address = request.POST.get('pickup_address', load.pickup_address)
            load.pickup_phone = request.POST.get('pickup_phone', load.pickup_phone)
            load.pickup_email = request.POST.get('pickup_email', load.pickup_email)
            load.pickup_instructions = request.POST.get('pickup_instructions', load.pickup_instructions)
            load.pickup_internal_notes = request.POST.get('pickup_internal_notes', load.pickup_internal_notes)
            load.delivery_name = request.POST.get('delivery_name', load.delivery_name)
            load.delivery_date = request.POST.get('delivery_date') or load.delivery_date
            load.delivery_appointment_time = request.POST.get('delivery_appointment_time') or load.delivery_appointment_time
            load.delivery_city = request.POST.get('delivery_city', load.delivery_city)
            load.delivery_state = request.POST.get('delivery_state', load.delivery_state)
            load.delivery_zip = request.POST.get('delivery_zip', load.delivery_zip)
            load.delivery_address = request.POST.get('delivery_address', load.delivery_address)
            load.delivery_phone = request.POST.get('delivery_phone', load.delivery_phone)
            load.delivery_email = request.POST.get('delivery_email', load.delivery_email)
            load.delivery_instructions = request.POST.get('delivery_instructions', load.delivery_instructions)
            load.cust_miles = cust_miles
            load.cust_rate = 0.00
            load.carr_miles = carr_miles
            load.carr_rate = 0.00
            load.cust_amt = cust_amt
            load.carr_amt = carr_amt
            load.total_miles = int(request.POST.get('total_miles', load.total_miles) or '0')
            load.total_amount = float(request.POST.get('total_amount', load.total_amount) or '0.00')
            load.driver_1 = request.POST.get('driver_1', load.driver_1)
            load.driver_1_cell = request.POST.get('driver_1_cell', load.driver_1_cell)
            load.driver_2 = request.POST.get('driver_2', load.driver_2)
            load.driver_2_cell = request.POST.get('driver_2_cell', load.driver_2_cell)
            load.truck_number = request.POST.get('truck_number', load.truck_number)
            load.trailer_number = request.POST.get('trailer_number', load.trailer_number)

            if load.carrier and load.status == 'ACTIVE':
                load.status = 'BOOKED'

            load.save()
            print("Updated load:", load.__dict__)

            # Delete existing commodities and create new ones
            load.commodities.all().delete()
            commodity_types = request.POST.getlist('commodity_type[]')
            commodity_descriptions = request.POST.getlist('commodity_description[]')
            commodity_quantities = request.POST.getlist('commodity_qty[]')
            commodity_weights = request.POST.getlist('commodity_weight[]')
            commodity_values = request.POST.getlist('commodity_value[]')

            for type, desc, qty, weight, value in zip(commodity_types, commodity_descriptions, commodity_quantities, commodity_weights, commodity_values):
                if desc and qty:  # Ensure required fields are not empty (type is optional)
                    try:
                        commodity = Commodity.objects.create(
                            load=load,
                            type=type if type else '',
                            description=desc,
                            quantity=int(qty),
                            weight=float(weight) if weight else 0.0,
                            value=float(value) if value else 0.00
                        )
                        print("Created commodity:", commodity.__dict__)
                    except ValueError as e:
                        print("Error creating commodity:", str(e))
                        messages.error(request, f'Invalid commodity data: {str(e)}')

            # Delete existing additional pickups and create new ones
            load.additional_pickups.all().delete()
            additional_pickup_names = request.POST.getlist('additional_pickup_name[]')
            additional_pickup_addresses = request.POST.getlist('additional_pickup_address[]')
            additional_pickup_cities = request.POST.getlist('additional_pickup_city[]')
            additional_pickup_states = request.POST.getlist('additional_pickup_state[]')
            additional_pickup_zips = request.POST.getlist('additional_pickup_zip[]')
            additional_pickup_dates = request.POST.getlist('additional_pickup_date[]')
            additional_pickup_phones = request.POST.getlist('additional_pickup_phone[]')
            additional_pickup_emails = request.POST.getlist('additional_pickup_email[]')
            additional_pickup_appointment_times = request.POST.getlist('additional_pickup_appointment_time[]')
            additional_pickup_instructions = request.POST.getlist('additional_pickup_instructions[]')

            for name, addr, city, state, zip_code, date, phone, email, time, instr in zip(
                additional_pickup_names, additional_pickup_addresses, additional_pickup_cities,
                additional_pickup_states, additional_pickup_zips, additional_pickup_dates,
                additional_pickup_phones, additional_pickup_emails, additional_pickup_appointment_times,
                additional_pickup_instructions
            ):
                if addr:  # Ensure address is not empty
                    pickup = AdditionalPickup.objects.create(
                        load=load,
                        name=name,
                        address=addr,
                        city=city,
                        state=state,
                        zip=zip_code,
                        date=date or None,
                        phone=phone,
                        email=email,
                        appointment_time=time,
                        instructions=instr
                    )
                    print("Created additional pickup:", pickup.__dict__)

            # Delete existing additional deliveries and create new ones
            load.additional_deliveries.all().delete()
            additional_delivery_names = request.POST.getlist('additional_delivery_name[]')
            additional_delivery_addresses = request.POST.getlist('additional_delivery_address[]')
            additional_delivery_cities = request.POST.getlist('additional_delivery_city[]')
            additional_delivery_states = request.POST.getlist('additional_delivery_state[]')
            additional_delivery_zips = request.POST.getlist('additional_delivery_zip[]')
            additional_delivery_dates = request.POST.getlist('additional_delivery_date[]')
            additional_delivery_phones = request.POST.getlist('additional_delivery_phone[]')
            additional_delivery_emails = request.POST.getlist('additional_delivery_email[]')
            additional_delivery_appointment_times = request.POST.getlist('additional_delivery_appointment_time[]')
            additional_delivery_instructions = request.POST.getlist('additional_delivery_instructions[]')

            for name, addr, city, state, zip_code, date, phone, email, time, instr in zip(
                additional_delivery_names, additional_delivery_addresses, additional_delivery_cities,
                additional_delivery_states, additional_delivery_zips, additional_delivery_dates,
                additional_delivery_phones, additional_delivery_emails, additional_delivery_appointment_times,
                additional_delivery_instructions
            ):
                if addr:  # Ensure address is not empty
                    delivery = AdditionalDelivery.objects.create(
                        load=load,
                        name=name,
                        address=addr,
                        city=city,
                        state=state,
                        zip=zip_code,
                        date=date or None,
                        phone=phone,
                        email=email,
                        appointment_time=time,
                        instructions=instr
                    )
                    print("Created additional delivery:", delivery.__dict__)

            messages.success(request, f'Load #{load.load_number} updated successfully.')
            return redirect('my_loads')

        except (ValueError, ValidationError) as e:
            print("Error updating load:", str(e))
            messages.error(request, f'Error updating load: {str(e)}')
            return render(request, 'edit_load.html', {
                'company_info': company_info,
                'company': company,
                'load': load,
                'load_id': load_id,
                'customers': customers,
                'onboarded_carriers': onboarded_carriers
            })

    return render(request, 'edit_load.html', {
        'company_info': company_info,
        'company': company,
        'load': load,
        'load_id': load_id,
        'customers': customers,
        'onboarded_carriers': onboarded_carriers
    })

@approved_required
def carrier_info(request, carrier_id):
    company_info, created = CompanyInfo.objects.get_or_create(user=request.user)
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
        print("POST data:", request.POST)
        print("FILES data:", request.FILES)
        form_type = request.POST.get('form_type')

        if form_type == 'carrier_details':
            try:
                carrier.legal_name = request.POST.get('legal_name', carrier.legal_name)
                carrier.mc_number = request.POST.get('mc_number', carrier.mc_number)
                carrier.dot_number = request.POST.get('dot_number', carrier.dot_number)
                carrier.email = request.POST.get('email', carrier.email)
                carrier.phone = request.POST.get('phone', carrier.phone)
                carrier.ein_number = request.POST.get('ein_number', carrier.ein_number)
                carrier.company_officer = request.POST.get('company_officer', carrier.company_officer)
                carrier.address = request.POST.get('address', carrier.address)
                carrier.contact_person = request.POST.get('contact_person', carrier.contact_person)
                carrier.status = request.POST.get('status', carrier.status)
                carrier.save()
                print("Updated carrier:", carrier.__dict__)
                messages.success(request, 'Carrier details updated successfully.')
                return redirect('carrier_info', carrier_id=carrier.id)
            except ValidationError as e:
                print("Error updating carrier details:", str(e))
                messages.error(request, f'Error updating carrier details: {str(e)}')

        elif form_type == 'file_upload':
            files = request.FILES.getlist('files')
            if files:
                for file in files:
                    carrier_file = CarrierFile.objects.create(carrier=carrier, file=file)
                    print("Uploaded file:", carrier_file.__dict__)
                messages.success(request, f'{len(files)} file(s) uploaded successfully.')
            else:
                messages.error(request, 'No files selected for upload.')
            return redirect('carrier_info', carrier_id=carrier.id)

        elif form_type == 'delete_file':
            file_id = request.POST.get('file_id')
            try:
                file = CarrierFile.objects.get(id=file_id, carrier=carrier)
                file.delete()
                messages.success(request, 'File deleted successfully.')
            except CarrierFile.DoesNotExist:
                messages.error(request, 'File not found.')
            return redirect('carrier_info', carrier_id=carrier.id)

        else:
            messages.error(request, 'Invalid form submission.')
            return redirect('carrier_info', carrier_id=carrier.id)

    return render(request, 'carrier_info.html', {
        'company_info': company_info,
        'company': company,
        'carrier': carrier,
    })
