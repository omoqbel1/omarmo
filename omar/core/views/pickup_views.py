from django.shortcuts import render, redirect, get_object_or_404
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.contrib import messages

from core.models import CompanyInfo, Company, Load, AdditionalPickup, AdditionalDelivery
from core.decorators import approved_required

@approved_required
def delete_pickup(request, pickup_id):
    try:
        pickup = get_object_or_404(AdditionalPickup, id=pickup_id)
        load = pickup.load
        pickup.delete()
        messages.success(request, 'Additional pickup deleted successfully.')
        return redirect('edit_load', load_id=load.load_number)
    except Exception as e:
        messages.error(request, f'Error deleting pickup: {str(e)}')
        return redirect('my_loads')

@approved_required
def delete_delivery(request, delivery_id):
    try:
        delivery = get_object_or_404(AdditionalDelivery, id=delivery_id)
        load = delivery.load
        delivery.delete()
        messages.success(request, 'Additional delivery deleted successfully.')
        return redirect('edit_load', load_id=load.load_number)
    except Exception as e:
        messages.error(request, f'Error deleting delivery: {str(e)}')
        return redirect('my_loads')
