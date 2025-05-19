from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib import messages

from core.models import CompanyInfo, Company, Customer
from core.decorators import approved_required

@approved_required
def my_customers(request):
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

    customers = Customer.objects.filter(company=company).order_by('customer_id')

    return render(request, 'my_customers.html', {
        'company_info': company_info,
        'company': company,
        'customers': customers
    })

@approved_required
def add_customer(request):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
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
            messages.success(request, f'Customer {customer.name} added successfully.')
            return redirect('my_customers')
        except ValidationError as e:
            messages.error(request, f'Error adding customer: {str(e)}')

    return render(request, 'add_customer.html', {
        'company_info': company_info,
        'company': company
    })

@approved_required
def edit_customer(request, customer_id):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
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
        try:
            customer.company_name = request.POST.get('company_name', customer.company_name)
            customer.name = request.POST.get('name', customer.name) or 'Unknown Customer'
            customer.address = request.POST.get('address', customer.address)
            customer.city = request.POST.get('city', customer.city)
            customer.state = request.POST.get('state', customer.state)
            customer.zip = request.POST.get('zip', customer.zip)
            customer.phone = request.POST.get('phone', customer.phone)
            customer.email = request.POST.get('email', customer.email)
            customer.save()
            messages.success(request, f'Customer {customer.name} updated successfully.')
            return redirect('my_customers')
        except ValidationError as e:
            messages.error(request, f'Error updating customer: {str(e)}')

    return render(request, 'edit_customer.html', {
        'company_info': company_info,
        'company': company,
        'customer': customer,
        'customer_id': customer_id
    })

@approved_required
def delete_customer(request, customer_id):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
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
