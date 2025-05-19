from .auth_views import signup, login_view, logout_view
from .dashboard_views import dashboard
from .carrier_views import (
    save_carrier,
    saved_carriers,
    delete_carrier,
    edit_carrier,
    onboarded_carriers,
    onboard_carrier,
    carrier_info,
)
from .load_views import my_loads, add_load, edit_load, delete_load
from .ratecon_views import generate_rate_confirmation
from .customer_views import my_customers, add_customer, edit_customer, delete_customer
from .settings_views import settings, delete_logo, manage_users
from .pickup_views import delete_pickup, delete_delivery
from .utility_views import fmcsa_lookup, upload_carrier_file, delete_carrier_file
from .copy_views import copy_load
from .fetch_insurance_new import fetch_carrier_insurance, check_insurance_status
