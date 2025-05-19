from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib import messages
from django.http import HttpResponse
from core.models import CompanyInfo, Company, Load, Customer, SavedCarrier, Commodity, AdditionalPickup, AdditionalDelivery
from core.decorators import approved_required
from weasyprint import HTML
from django.template.loader import render_to_string
from datetime import datetime

@approved_required
def my_loads(request):
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
def add_load(request):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
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
    onboarded_carriers = SavedCarrier.objects.filter(company=company, is_onboarded=True).order_by('legal_name')

    if request.method == 'POST':
        customer_name = request.POST.get('customer_name', '').strip()
        if not customer_name:
            messages.error(request, 'Please select a customer.')
            return render(request, 'add_load.html', {
                'company_info': company_info,
                'company': company,
                'customers': customers,
                'onboarded_carriers': onboarded_carriers
            })

        if not Customer.objects.filter(company=company, name__iexact=customer_name).exists():
            messages.error(request, f'Customer "{customer_name}" does not exist.')
            return render(request, 'add_load.html', {
                'company_info': company_info,
                'company': company,
                'customers': customers,
                'onboarded_carriers': onboarded_carriers
            })

        try:
            # Use the next_load_number from company_info instead of querying for the last load
            next_load_number = company_info.next_load_number

            pickup_date = request.POST.get('pickup_date') or None
            delivery_date = request.POST.get('delivery_date') or None
            pickup_appointment_time = request.POST.get('pickup_appointment_time') or None
            delivery_appointment_time = request.POST.get('delivery_appointment_time') or None
            cust_miles = int(request.POST.get('cust_miles', '0') or '0')
            carr_miles = int(request.POST.get('carr_miles', '0') or '0')
            cust_amt = float(request.POST.get('cust_amt', '0.00') or '0.00')
            carr_amt = float(request.POST.get('carr_amt', '0.00') or '0.00')

            carrier_id = request.POST.get('carrier')
            carrier_name = ''
            if carrier_id:
                try:
                    carrier = SavedCarrier.objects.get(id=carrier_id, company=company, is_onboarded=True)
                    carrier_name = carrier.legal_name
                except SavedCarrier.DoesNotExist:
                    messages.error(request, 'Selected carrier is not onboarded or does not exist.')
                    return render(request, 'add_load.html', {
                        'company_info': company_info,
                        'company': company,
                        'customers': customers,
                        'onboarded_carriers': onboarded_carriers
                    })

            load = Load.objects.create(
                company=company,
                load_number=next_load_number,
                status='BOOKED' if carrier_name else 'ACTIVE',
                customer=customer_name,
                carrier=carrier_name,
                pickup_name=request.POST.get('pickup_name', ''),
                pickup_date=pickup_date,
                pickup_appointment_time=pickup_appointment_time,
                pickup_city=request.POST.get('pickup_city', ''),
                pickup_state=request.POST.get('pickup_state', ''),
                pickup_zip=request.POST.get('pickup_zip', ''),
                pickup_address=request.POST.get('pickup_address', ''),
                pickup_phone=request.POST.get('pickup_phone', ''),
                pickup_email=request.POST.get('pickup_email', ''),
                pickup_instructions=request.POST.get('pickup_instructions', ''),
                pickup_internal_notes=request.POST.get('pickup_internal_notes', ''),
                delivery_name=request.POST.get('delivery_name', ''),
                delivery_date=delivery_date,
                delivery_appointment_time=delivery_appointment_time,
                delivery_city=request.POST.get('delivery_city', ''),
                delivery_state=request.POST.get('delivery_state', ''),
                delivery_zip=request.POST.get('delivery_zip', ''),
                delivery_address=request.POST.get('delivery_address', ''),
                delivery_phone=request.POST.get('delivery_phone', ''),
                delivery_email=request.POST.get('delivery_email', ''),
                delivery_instructions=request.POST.get('delivery_instructions', ''),
                cust_miles=cust_miles,
                carr_miles=carr_miles,
                cust_amt=cust_amt,
                carr_amt=carr_amt,
                total_miles=int(request.POST.get('total_miles', '0') or '0'),
                total_amount=float(request.POST.get('total_amount', '0.00') or '0.00'),
                driver_1=request.POST.get('driver_1', ''),
                driver_1_cell=request.POST.get('driver_1_cell', ''),
                driver_2=request.POST.get('driver_2', ''),
                driver_2_cell=request.POST.get('driver_2_cell', ''),
                truck_number=request.POST.get('truck_number', ''),
                trailer_number=request.POST.get('trailer_number', ''),
            )

            # Increment the next_load_number for future loads
            company_info.next_load_number += 1
            company_info.save()

            commodity_types = request.POST.getlist('commodity_type[]')
            commodity_descriptions = request.POST.getlist('commodity_description[]')
            commodity_quantities = request.POST.getlist('commodity_qty[]')
            commodity_weights = request.POST.getlist('commodity_weight[]')
            commodity_values = request.POST.getlist('commodity_value[]')

            for type, desc, qty, weight, value in zip(commodity_types, commodity_descriptions, commodity_quantities, commodity_weights, commodity_values):
                if desc and qty:
                    try:
                        Commodity.objects.create(
                            load=load,
                            type=type if type else '',
                            description=desc,
                            quantity=int(qty),
                            weight=float(weight) if weight else 0.0,
                            value=float(value) if value else 0.00
                        )
                    except ValueError as e:
                        messages.error(request, f'Invalid commodity data: {str(e)}')

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
                if addr:
                    AdditionalPickup.objects.create(
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
                if addr:
                    AdditionalDelivery.objects.create(
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

            messages.success(request, f'Load #{load.load_number} added successfully.')
            return redirect('my_loads')

        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error adding load: {str(e)}')

    return render(request, 'add_load.html', {
        'company_info': company_info,
        'company': company,
        'customers': customers,
        'onboarded_carriers': onboarded_carriers
    })

@approved_required
def edit_load(request, load_id):
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)
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
    onboarded_carriers = SavedCarrier.objects.filter(company=company, is_onboarded=True).order_by('legal_name')

    if request.method == 'POST':
        # Store the redirect URL if provided
        redirect_after_save = request.POST.get('redirect_after_save')
        stay_on_page = request.POST.get('stay_on_page') == 'true'

        customer_name = request.POST.get('customer_name', '').strip()
        if not customer_name:
            messages.error(request, 'Please select a customer.')
            return render(request, 'edit_load.html', {
                'company_info': company_info,
                'company': company,
                'load': load,
                'load_id': load_id,
                'customers': customers,
                'onboarded_carriers': onboarded_carriers
            })

        if not Customer.objects.filter(company=company, name__iexact=customer_name).exists():
            messages.error(request, f'Customer "{customer_name}" does not exist.')
            return render(request, 'edit_load.html', {
                'company_info': company_info,
                'company': company,
                'load': load,
                'load_id': load_id,
                'customers': customers,
                'onboarded_carriers': onboarded_carriers
            })

        try:
            carrier_name = load.carrier
            if 'carrier' in request.POST and request.POST['carrier']:
                try:
                    carrier = SavedCarrier.objects.get(id=request.POST['carrier'], company=company, is_onboarded=True)
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
            load.cust_miles = int(request.POST.get('cust_miles', load.cust_miles) or '0')
            load.carr_miles = int(request.POST.get('carr_miles', load.carr_miles) or '0')
            load.cust_amt = float(request.POST.get('cust_amt', load.cust_amt) or '0.00')
            load.carr_amt = float(request.POST.get('carr_amt', load.carr_amt) or '0.00')
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

            load.commodities.all().delete()
            commodity_types = request.POST.getlist('commodity_type[]')
            commodity_descriptions = request.POST.getlist('commodity_description[]')
            commodity_quantities = request.POST.getlist('commodity_qty[]')
            commodity_weights = request.POST.getlist('commodity_weight[]')
            commodity_values = request.POST.getlist('commodity_value[]')

            for type, desc, qty, weight, value in zip(commodity_types, commodity_descriptions, commodity_quantities, commodity_weights, commodity_values):
                if desc and qty:
                    try:
                        Commodity.objects.create(
                            load=load,
                            type=type if type else '',
                            description=desc,
                            quantity=int(qty),
                            weight=float(weight) if weight else 0.0,
                            value=float(value) if value else 0.00
                        )
                    except ValueError as e:
                        messages.error(request, f'Invalid commodity data: {str(e)}')

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
                if addr:
                    AdditionalPickup.objects.create(
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
                if addr:
                    AdditionalDelivery.objects.create(
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

            messages.success(request, f'Load #{load.load_number} updated successfully.')

            # Check if we need to redirect after saving
            if redirect_after_save:
                return redirect(redirect_after_save)
            elif stay_on_page:
                # Re-fetch the load to get the updated data
                load = get_object_or_404(Load, company=company, load_number=load_id)
                return render(request, 'edit_load.html', {
                    'company_info': company_info,
                    'company': company,
                    'load': load,
                    'load_id': load_id,
                    'customers': customers,
                    'onboarded_carriers': onboarded_carriers
                })
            else:
                return redirect('my_loads')

        except (ValueError, ValidationError) as e:
            messages.error(request, f'Error updating load: {str(e)}')

    return render(request, 'edit_load.html', {
        'company_info': company_info,
        'company': company,
        'load': load,
        'load_id': load_id,
        'customers': customers,
        'onboarded_carriers': onboarded_carriers
    })
    
@approved_required
def delete_load(request, load_id):
    # Fix the syntax error: replace * with _
    company_info, _ = CompanyInfo.objects.get_or_create(user=request.user)

    company_id = request.session.get('company_id')
    if not company_id:
        messages.error(request, 'Company ID not found in session.')
        return redirect('my_loads')

    try:
        company = Company.objects.get(id=company_id)
        # Also modify this line to look up by load_number instead of id
        load = get_object_or_404(Load, load_number=load_id, company_id=company_id)
        load.delete()
        messages.success(request, 'Load deleted successfully.')
    except ObjectDoesNotExist:
        messages.error(request, 'Load not found.')

    return redirect('my_loads')
