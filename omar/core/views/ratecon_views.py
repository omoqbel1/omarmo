from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from weasyprint import HTML
from datetime import datetime

# Fix these import paths to match your project structure
from core.models import CompanyInfo, Company, Load, SavedCarrier
from core.decorators import approved_required

@approved_required
def generate_rate_confirmation(request, load_id):
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

    # Fetch carrier details if available
    carrier = None
    if load.carrier:
        try:
            carrier = SavedCarrier.objects.get(legal_name=load.carrier, company=company, is_onboarded=True)
        except SavedCarrier.DoesNotExist:
            carrier = None

    # Calculate total weight from commodities
    total_weight = sum(commodity.weight for commodity in load.commodities.all())

    # Prepare pickup and delivery information
    pickup_addresses = []
    pickup_dates = []
    pickup_times = []
    pickup_instructions = []  # Add for pickup instructions

    # Main pickup - check for address instead of name
    if load.pickup_address:
        pickup_address = f"{load.pickup_name or ''}, {load.pickup_address}, {load.pickup_city}, {load.pickup_state} {load.pickup_zip}"
        if load.pickup_phone:
            pickup_address += f"<br>Phone: {load.pickup_phone}"
        pickup_addresses.append(pickup_address)
        pickup_dates.append(load.pickup_date.strftime('%m/%d/%Y') if load.pickup_date else "")
        pickup_instructions.append(load.pickup_instructions or "")  # Add pickup instructions

        # Format time from 24-hour to 12-hour
        pickup_time = ""
        if load.pickup_appointment_time:
            try:
                # Try with seconds format first
                time_obj = datetime.strptime(str(load.pickup_appointment_time), '%H:%M:%S')
                pickup_time = time_obj.strftime('%I:%M %p')
            except ValueError:
                # If that fails, try without seconds
                try:
                    time_obj = datetime.strptime(str(load.pickup_appointment_time), '%H:%M')
                    pickup_time = time_obj.strftime('%I:%M %p')
                except ValueError:
                    # If still failing, just display as is
                    pickup_time = str(load.pickup_appointment_time)
        pickup_times.append(pickup_time)

    # Additional pickups
    for pickup in load.additional_pickups.all():
        # Check for address instead of name
        if pickup.address:
            pickup_address = f"{pickup.name or ''}, {pickup.address}, {pickup.city}, {pickup.state} {pickup.zip}"
            if pickup.phone:
                pickup_address += f"<br>Phone: {pickup.phone}"
            pickup_addresses.append(pickup_address)
            pickup_dates.append(pickup.date.strftime('%m/%d/%Y') if pickup.date else "")
            pickup_instructions.append(pickup.instructions or "")  # Add pickup instructions

            # Format time from 24-hour to 12-hour - START WITH EMPTY STRING FOR EACH PICKUP
            additional_pickup_time = ""  # Use a different variable name
            if pickup.appointment_time:
                try:
                    # Try with seconds format first
                    time_obj = datetime.strptime(str(pickup.appointment_time), '%H:%M:%S')
                    additional_pickup_time = time_obj.strftime('%I:%M %p')
                except ValueError:
                    # If that fails, try without seconds
                    try:
                        time_obj = datetime.strptime(str(pickup.appointment_time), '%H:%M')
                        additional_pickup_time = time_obj.strftime('%I:%M %p')
                    except ValueError:
                        # If still failing, just display as is
                        additional_pickup_time = str(pickup.appointment_time)
            pickup_times.append(additional_pickup_time)  # Make sure this is within the loop for each pickup

    # Prepare delivery information
    delivery_addresses = []
    delivery_dates = []
    delivery_times = []
    delivery_instructions = []  # Add for delivery instructions

    # Main delivery
    if load.delivery_address:
        delivery_address = f"{load.delivery_name or ''}, {load.delivery_address}, {load.delivery_city}, {load.delivery_state} {load.delivery_zip}"
        if load.delivery_phone:
            delivery_address += f"<br>Phone: {load.delivery_phone}"
        delivery_addresses.append(delivery_address)
        delivery_dates.append(load.delivery_date.strftime('%m/%d/%Y') if load.delivery_date else "")
        delivery_instructions.append(load.delivery_instructions or "")  # Add delivery instructions

        # Format time from 24-hour to 12-hour
        delivery_time = ""
        if load.delivery_appointment_time:
            try:
                # Try with seconds format first
                time_obj = datetime.strptime(str(load.delivery_appointment_time), '%H:%M:%S')
                delivery_time = time_obj.strftime('%I:%M %p')
            except ValueError:
                # If that fails, try without seconds
                try:
                    time_obj = datetime.strptime(str(load.delivery_appointment_time), '%H:%M')
                    delivery_time = time_obj.strftime('%I:%M %p')
                except ValueError:
                    # If still failing, just display as is
                    delivery_time = str(load.delivery_appointment_time)
        delivery_times.append(delivery_time)

    # Additional deliveries
    for delivery in load.additional_deliveries.all():
        if delivery.address:
            delivery_address = f"{delivery.name or ''}, {delivery.address}, {delivery.city}, {delivery.state} {delivery.zip}"
            if delivery.phone:
                delivery_address += f"<br>Phone: {delivery.phone}"
            delivery_addresses.append(delivery_address)
            delivery_dates.append(delivery.date.strftime('%m/%d/%Y') if delivery.date else "")
            delivery_instructions.append(delivery.instructions or "")  # Add delivery instructions

            # Format time from 24-hour to 12-hour
            additional_delivery_time = ""  # Use a different variable name
            if delivery.appointment_time:
                try:
                    # Try with seconds format first
                    time_obj = datetime.strptime(str(delivery.appointment_time), '%H:%M:%S')
                    additional_delivery_time = time_obj.strftime('%I:%M %p')
                except ValueError:
                    # If that fails, try without seconds
                    try:
                        time_obj = datetime.strptime(str(delivery.appointment_time), '%H:%M')
                        additional_delivery_time = time_obj.strftime('%I:%M %p')
                    except ValueError:
                        # If still failing, just display as is
                        additional_delivery_time = str(delivery.appointment_time)
            delivery_times.append(additional_delivery_time)

    # Combine any remaining internal notes
    internal_notes = []
    if load.pickup_internal_notes:
        internal_notes.append(load.pickup_internal_notes)
    internal_notes_text = "\n".join(internal_notes) if internal_notes else ""

    # Process carrier terms to ensure proper formatting
    carrier_terms = company_info.carrier_terms or ""

    # Check if carrier terms are already in HTML format (starts with <ol> or similar)
    is_html = False
    if carrier_terms and (carrier_terms.strip().startswith('<ol>') or
                          carrier_terms.strip().startswith('<ul>') or
                          carrier_terms.strip().startswith('<p>')):
        is_html = True

    # If not HTML, format it as an ordered list if it contains numbered items
    if not is_html and carrier_terms:
        lines = carrier_terms.strip().split('\n')
        # Check if lines start with numbers like "1.", "2.", etc.
        if lines and any(line.strip() and line.strip()[0].isdigit() and '.' in line[:5] for line in lines):
            formatted_terms = "<ol>\n"
            current_item = ""
            for line in lines:
                line = line.strip()
                if line and line[0].isdigit() and '.' in line[:5]:
                    # If we have a current item, add it to the formatted terms
                    if current_item:
                        formatted_terms += f"<li>{current_item}</li>\n"
                    # Start a new item
                    current_item = line[line.index('.')+1:].strip()
                elif line:
                    # Continue the current item
                    if current_item:
                        current_item += ' ' + line
                    else:
                        current_item = line
            # Add the last item
            if current_item:
                formatted_terms += f"<li>{current_item}</li>\n"
            formatted_terms += "</ol>"
            carrier_terms = formatted_terms

    # Prepare context data for the template
    context = {
        'LoadNumber': load.load_number,
        'OrderDate': datetime.now().strftime('%m/%d/%Y'),
        'Amount': f"${load.carr_amt:.2f}" if load.carr_amt else "$0.00",
        'CompanyName': company_info.company_name or "",
        'CompanyAddress': company_info.address1 or "",
        'CompanyCityStateZip': f"{company_info.city}, {company_info.state} {company_info.zip_code}" if company_info.city else "",
        'CompanyPhone': company_info.phone or "",
        'CompanyFax': company_info.fax or "",
        'CompanyEmail': company_info.email or "",
        'CompanyContact': company_info.contact or "",
        'CompanyMCNumber': company_info.mc_scac or "",  # Add the MC/SCAC number
        'CompanyLogo': company_info.logo if company_info.logo else None,
        'CompanyLogoURL': request.build_absolute_uri(company_info.logo.url) if company_info.logo and hasattr(company_info.logo, 'url') else None,
        'CarrierName': load.carrier or "",
        'CarrierAddress': carrier.street if carrier else "",
        'CarrierCityStateZip': f"{carrier.city}, {carrier.state} {carrier.zip_code}" if carrier and carrier.city else "",
        'CarrierPhone': carrier.phone if carrier else "",
        'CarrierEmail': carrier.email if carrier else "",
        'CarrierMCNumber': carrier.mc_number if carrier else "",
        'Driver1': load.driver_1 or "",
        'Driver1Cell': load.driver_1_cell or "",
        'Driver2': load.driver_2 or "",
        'Driver2Cell': load.driver_2_cell or "",
        'TruckNumber': load.truck_number or "",
        'TrailerNumber': load.trailer_number or "",
        'TotalMiles': load.total_miles or "",
        'RefNo': "",
        'TotalWeight': f"{total_weight:.1f} lbs" if total_weight else "",
        'Instructions': internal_notes_text,
        'CarrierTerms': carrier_terms,

        # Data for the table with stops
        'PickupAddresses': pickup_addresses,
        'PickupDates': pickup_dates,
        'PickupTimes': pickup_times,
        'PickupInstructions': pickup_instructions,
        'DeliveryAddresses': delivery_addresses,
        'DeliveryDates': delivery_dates,
        'DeliveryTimes': delivery_times,
        'DeliveryInstructions': delivery_instructions,
    }

    try:
        # Render to HTML
        html_content = render_to_string('rate_confirmation.html', context)

        # Generate PDF
        pdf_file = HTML(string=html_content).write_pdf()

        # Serve PDF
        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = f'inline; filename="rate_confirmation_{load.load_number}.pdf"'
        response.write(pdf_file)
        return response

    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('my_loads')
