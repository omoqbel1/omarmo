# Fixed copy_views.py handling NOT NULL constraint on carrier field

from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse
from ..models import Load  # Correct parent directory import

def copy_load(request, load_id):
    """
    Create a copy of an existing load with optional modifications
    """
    # Get the original load or return 404
    original_load = get_object_or_404(Load, load_number=load_id)

    if request.method == 'POST':
        # Get values from the form
        new_status = request.POST.get('new_status', original_load.status)
        reset_carrier = request.POST.get('reset_carrier') == '1'
        reset_dates = request.POST.get('reset_dates') == '1'

        # Create a new load as a copy
        new_load = Load()

        # Manually copy non-primary key fields from the original load
        exclude_fields = ['id', 'pk', 'load_number']

        # Loop through all fields in the model and copy values
        for field in original_load._meta.fields:
            if field.name not in exclude_fields:
                setattr(new_load, field.name, getattr(original_load, field.name))

        # Apply requested modifications
        new_load.status = new_status

        # Reset carrier information if requested
        if reset_carrier:
            # Check if carrier is a required field in your model
            carrier_field = Load._meta.get_field('carrier')
            if not carrier_field.null and carrier_field.blank:
                # Field doesn't allow NULL but allows blank - set to empty string
                new_load.carrier = ""
            elif carrier_field.null:
                # Field allows NULL - set to None
                new_load.carrier = None
            else:
                # Field is required and doesn't allow NULL or blank
                # Keep the original value or set a default placeholder
                # new_load.carrier = "PENDING ASSIGNMENT"
                pass

            # Reset carrier amount (this should work as numeric fields typically allow NULL)
            new_load.carr_amt = 0.00

        # Reset dates if requested
        if reset_dates:
            # Check if these fields allow NULL
            if Load._meta.get_field('pickup_date').null:
                new_load.pickup_date = None
            if Load._meta.get_field('delivery_date').null:
                new_load.delivery_date = None

        # Generate a new load number
        from django.db.models import Max
        max_load = Load.objects.aggregate(Max('load_number'))['load_number__max']
        new_load.load_number = max_load + 1 if max_load else 1001

        # Save the new load
        new_load.save()

        # Add success message
        messages.success(request, f'Load #{original_load.load_number} copied to #{new_load.load_number}')

        # Redirect to the edit page for the new load
        return redirect('edit_load', load_id=new_load.load_number)

    # If not POST, redirect to loads list
    return redirect('my_loads')
