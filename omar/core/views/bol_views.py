from django.shortcuts import get_object_or_404, redirect
from django.http import HttpResponse
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.template.loader import render_to_string
from weasyprint import HTML
from datetime import datetime
import io

# Import your models
from core.models import CompanyInfo, Company, Load, SavedCarrier
from core.decorators import approved_required

@approved_required
def generate_bol(request, load_id):
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

    # Calculate total quantity
    total_qty = sum(commodity.quantity for commodity in load.commodities.all())

    # Get commodities for BOL, filtering out zero values
    commodities = []
    for commodity in load.commodities.all():
        if commodity.quantity > 0:  # Only include commodities with quantity > 0
            # Don't include zero values
            value = commodity.value
            if value == 0 or value == 0.0 or value == "0" or value == "0.0" or value == "0.00":
                value = ""

            commodities.append({
                'type': commodity.type or '',
                'description': commodity.description or '',
                'quantity': commodity.quantity,
                'weight': commodity.weight,
                'value': value
            })

    # Prepare pickup information
    pickups = []

    # Main pickup
    if load.pickup_address:
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

        pickups.append({
            'name': load.pickup_name or "",
            'address': load.pickup_address or "",
            'city': load.pickup_city or "",
            'state': load.pickup_state or "",
            'zip': load.pickup_zip or "",
            'phone': load.pickup_phone or "",
            'date': load.pickup_date.strftime('%m/%d/%Y') if load.pickup_date else "",
            'time': pickup_time,
        })

    # Additional pickups
    for pickup in load.additional_pickups.all():
        if pickup.address:
            additional_pickup_time = ""
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

            pickups.append({
                'name': pickup.name or "",
                'address': pickup.address or "",
                'city': pickup.city or "",
                'state': pickup.state or "",
                'zip': pickup.zip or "",
                'phone': pickup.phone or "",
                'date': pickup.date.strftime('%m/%d/%Y') if pickup.date else "",
                'time': additional_pickup_time,
            })

    # Prepare delivery information for main and additional deliveries
    deliveries = []

    # Main delivery
    if load.delivery_address:
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

        deliveries.append({
            'name': load.delivery_name or "",
            'address': load.delivery_address or "",
            'city': load.delivery_city or "",
            'state': load.delivery_state or "",
            'zip': load.delivery_zip or "",
            'phone': load.delivery_phone or "",
            'date': load.delivery_date.strftime('%m/%d/%Y') if load.delivery_date else "",
            'time': delivery_time,
        })

    # Additional deliveries
    for delivery in load.additional_deliveries.all():
        if delivery.address:
            additional_delivery_time = ""
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

            deliveries.append({
                'name': delivery.name or "",
                'address': delivery.address or "",
                'city': delivery.city or "",
                'state': delivery.state or "",
                'zip': delivery.zip or "",
                'phone': delivery.phone or "",
                'date': delivery.date.strftime('%m/%d/%Y') if delivery.date else "",
                'time': additional_delivery_time,
            })

    try:
        # Create a list to store all the PDF files
        pdf_files = []
        bol_count = 1  # Counter for BOL numbering

        # Generate BOLs for all pickup-delivery combinations
        # This creates a matrix of all possible combinations (P×D total BOLs)
        for pickup_idx, pickup in enumerate(pickups):
            for delivery_idx, delivery in enumerate(deliveries):
                # Create a unique BOL number for each pickup-delivery combination
                if len(pickups) == 1 and len(deliveries) == 1:
                    bol_number = f"BOL-{load.load_number}"
                else:
                    bol_number = f"BOL-{load.load_number}-{bol_count}"
                    bol_count += 1

                # Prepare the page-specific context
                context = {
                    'BOLNumber': bol_number,
                    'LoadNumber': load.load_number,
                    'OrderDate': datetime.now().strftime('%m/%d/%Y'),
                    'CompanyName': company_info.company_name or "",
                    'CompanyAddress': company_info.address1 or "",
                    'CompanyCityStateZip': f"{company_info.city}, {company_info.state} {company_info.zip_code}" if company_info.city else "",
                    'CompanyPhone': company_info.phone or "",
                    'CompanyFax': company_info.fax or "",
                    'CompanyEmail': company_info.email or "",
                    'CompanyContact': company_info.contact or "",
                    'CompanyLogo': company_info.logo if company_info.logo else None,
                    'CompanyLogoURL': request.build_absolute_uri(company_info.logo.url) if company_info.logo and hasattr(company_info.logo, 'url') else None,
                    'CarrierName': load.carrier or "",
                    'CarrierAddress': carrier.street if carrier else "",
                    'CarrierCityStateZip': f"{carrier.city}, {carrier.state} {carrier.zip_code}" if carrier and carrier.city else "",
                    'CarrierPhone': carrier.phone if carrier else "",
                    'CarrierEmail': carrier.email if carrier else "",
                    'CarrierMCNumber': carrier.mc_number if carrier else "",
                    'Driver1': load.driver_1 or "",
                    'Driver2': load.driver_2 or "",
                    'TruckNumber': load.truck_number or "",
                    'TrailerNumber': load.trailer_number or "",
                    'TotalMiles': load.total_miles or "",
                    'TotalWeight': f"{total_weight:.1f}" if total_weight else "",
                    'TotalQty': total_qty,

                    # Shipper information (current pickup)
                    'ShipperName': pickup['name'],
                    'ShipperAddress': pickup['address'],
                    'ShipperCity': pickup['city'],
                    'ShipperState': pickup['state'],
                    'ShipperZip': pickup['zip'],
                    'ShipperPhone': pickup['phone'],
                    'ShipperDate': pickup['date'],
                    'ShipperTime': pickup['time'],

                    # Consignee information (current delivery)
                    'ConsigneeName': delivery['name'],
                    'ConsigneeAddress': delivery['address'],
                    'ConsigneeCity': delivery['city'],
                    'ConsigneeState': delivery['state'],
                    'ConsigneeZip': delivery['zip'],
                    'ConsigneePhone': delivery['phone'],
                    'ConsigneeDate': delivery['date'],
                    'ConsigneeTime': delivery['time'],

                    # Commodities
                    'Commodities': commodities,
                }

                # Render to HTML
                html_content = render_to_string('bill_of_lading.html', context)

                # Generate PDF for this pickup-delivery combination
                pdf_file = HTML(string=html_content).write_pdf()
                pdf_files.append(pdf_file)

        # Merge all PDFs into one response
        if len(pdf_files) == 1:
            # If there's only one PDF, just return it
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="bill_of_lading_{load.load_number}.pdf"'
            response.write(pdf_files[0])
            return response
        else:
            # For multiple PDFs, you need a PDF merger
            try:
                from PyPDF2 import PdfMerger

                merger = PdfMerger()
                for pdf in pdf_files:
                    merger.append(io.BytesIO(pdf))

                output = io.BytesIO()
                merger.write(output)
                merger.close()

                # Rewind the buffer and send the response
                output.seek(0)
                response = HttpResponse(content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="bill_of_lading_{load.load_number}.pdf"'
                response.write(output.getvalue())
                return response
            except ImportError:
                # If PyPDF2 is not available, just return the first PDF with a notice
                messages.warning(request, 'PyPDF2 library not found. Only the first BOL page is shown. Install PyPDF2 to merge multiple BOLs.')
                response = HttpResponse(content_type='application/pdf')
                response['Content-Disposition'] = f'inline; filename="bill_of_lading_{load.load_number}.pdf"'
                response.write(pdf_files[0])
                return response

    except Exception as e:
        messages.error(request, f'Error generating PDF: {str(e)}')
        return redirect('my_loads')
