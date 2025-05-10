from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('save-carrier/', views.save_carrier, name='save_carrier'),
    path('saved-carriers/', views.saved_carriers, name='saved_carriers'),
    path('delete-carrier/<int:carrier_id>/', views.delete_carrier, name='delete_carrier'),
    path('edit-carrier/<int:carrier_id>/', views.edit_carrier, name='edit_carrier'),
    path('settings/', views.settings, name='settings'),
    path('logout/', views.logout_view, name='logout'),  # Added logout route
]
