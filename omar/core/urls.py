# core/urls.py - Fixed with proper imports
from django.urls import path
from core import views
from core.views.bol_views import generate_bol  # Import your BOL view
from core.views.copy_views import copy_load  # Import copy_load directly like generate_bol
from core.views.fetch_insurance_new import fetch_carrier_insurance, check_insurance_status

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('save-carrier/', views.save_carrier, name='save_carrier'),
    path('saved-carriers/', views.saved_carriers, name='saved_carriers'),
    path('delete-carrier/<int:carrier_id>/', views.delete_carrier, name='delete_carrier'),
    path('edit-carrier/<int:carrier_id>/', views.edit_carrier, name='edit_carrier'),
    path('settings/', views.settings, name='settings'),
    path('delete-logo/', views.delete_logo, name='delete_logo'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup, name='signup'),
    path('login/', views.login_view, name='login'),
    path('manage-users/', views.manage_users, name='manage_users'),
    path('my-loads/', views.my_loads, name='my_loads'),
    path('add-load/', views.add_load, name='add_load'),
    path('edit-load/<int:load_id>/', views.edit_load, name='edit_load'),
    path('delete-load/<int:load_id>/', views.delete_load, name='delete_load'),
    path('my-customers/', views.my_customers, name='my_customers'),
    path('add-customer/', views.add_customer, name='add_customer'),
    path('edit-customer/<int:customer_id>/', views.edit_customer, name='edit_customer'),
    path('delete-customer/<int:customer_id>/', views.delete_customer, name='delete_customer'),
    path('onboarded-carriers/', views.onboarded_carriers, name='onboarded_carriers'),
    path('onboard-carrier/<int:carrier_id>/', views.onboard_carrier, name='onboard_carrier'),
    path('carrier-info/<int:carrier_id>/', views.carrier_info, name='carrier_info'),
    path('delete-pickup/<int:pickup_id>/', views.delete_pickup, name='delete_pickup'),
    path('delete-delivery/<int:delivery_id>/', views.delete_delivery, name='delete_delivery'),
    path('fmcsa-lookup/', views.fmcsa_lookup, name='fmcsa_lookup'),
    path('rate-confirmation/<int:load_id>/', views.generate_rate_confirmation, name='generate_rate_confirmation'),
    path('bill-of-lading/<int:load_id>/', generate_bol, name='generate_bol'),  # Bill of lading pattern
    path('copy-load/<int:load_id>/', copy_load, name='copy_load'),  # Copy load pattern
    # Insurance API endpoints
    path('api/carrier/fetch-insurance/', fetch_carrier_insurance, name='fetch_carrier_insurance'),
    path('api/carrier/check-insurance-status/', check_insurance_status, name='check_insurance_status'),
]
