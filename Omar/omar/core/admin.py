from django.contrib import admin
from django.utils.html import format_html
from .models import SavedCarrier, CompanyInfo

@admin.register(SavedCarrier)
class SavedCarrierAdmin(admin.ModelAdmin):
    list_display = ('legal_name', 'dot_number', 'mc_number', 'saved_at')

@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'logo_preview')

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 100px; max-width: 100px;" /></a>', obj.logo.url, obj.logo.url)
        return "No Image"
    logo_preview.short_description = 'Logo Preview'

    # Optional: Make the logo field editable in the admin
    fields = ('user', 'company_name', 'logo', 'contact', 'mc_scac', 'email', 'address1', 'address2', 'city', 'state', 'zip_code', 'phone', 'fax')
