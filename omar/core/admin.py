from django.contrib import admin
from django.utils.html import format_html
from django.contrib.auth.models import User
from .models import SavedCarrier, CompanyInfo, UserProfile, Company, Customer, Load

@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ('code', 'is_paused', 'user_count')  # Removed 'name'
    list_filter = ('is_paused',)  # Removed 'name'
    search_fields = ('code',)
    actions = ['pause_company', 'unpause_company']

    def user_count(self, obj):
        return UserProfile.objects.filter(company=obj).count()
    user_count.short_description = 'Number of Users'

    def pause_company(self, request, queryset):
        rows_updated = queryset.update(is_paused=True)
        self.message_user(request, f"{rows_updated} company(s) paused successfully. All users are now blocked from logging in.")
    pause_company.short_description = "Pause selected companies"

    def unpause_company(self, request, queryset):
        rows_updated = queryset.update(is_paused=False)
        self.message_user(request, f"{rows_updated} company(s) unpaused successfully. All users can now log in.")
    unpause_company.short_description = "Unpause selected companies"

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'is_approved', 'company', 'is_superuser_profile', 'created_at')
    list_filter = ('is_approved', 'company', 'is_superuser_profile')
    search_fields = ('user__username', 'user__email')
    actions = ['approve_users', 'disapprove_users']

    def created_at(self, obj):
        return obj.user.date_joined
    created_at.short_description = 'Created At'
    created_at.admin_order_field = 'user__date_joined'

    def approve_users(self, request, queryset):
        queryset.update(is_approved=True)
        for profile in queryset:
            profile.user.is_active = True
            profile.user.save()
        self.message_user(request, "Selected users have been approved and activated.")
    approve_users.short_description = "Approve selected users"

    def disapprove_users(self, request, queryset):
        queryset.update(is_approved=False)
        for profile in queryset:
            profile.user.is_active = False
            profile.user.save()
        self.message_user(request, "Selected users have been disapproved and deactivated.")
    disapprove_users.short_description = "Disapprove selected users"

@admin.register(SavedCarrier)
class SavedCarrierAdmin(admin.ModelAdmin):
    list_display = ('legal_name', 'dot_number', 'mc_number', 'company', 'saved_at', 'created_by')
    list_filter = ('company', 'saved_at')
    search_fields = ('legal_name', 'dot_number', 'mc_number', 'email', 'phone')

@admin.register(CompanyInfo)
class CompanyInfoAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'email', 'phone', 'logo_preview')
    list_filter = ('city', 'state')
    search_fields = ('company_name', 'user__username', 'email', 'phone')
    fields = ('user', 'company_name', 'logo', 'contact', 'mc_scac', 'email', 'address1', 'address2', 'city', 'state', 'zip_code', 'phone', 'fax')

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<a href="{}" target="_blank"><img src="{}" style="max-height: 100px; max-width: 100px;" /></a>', obj.logo.url, obj.logo.url)
        return "No Image"
    logo_preview.short_description = 'Logo Preview'

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_id', 'name', 'company', 'city', 'state', 'created_at')
    list_filter = ('company', 'created_at')
    search_fields = ('name', 'customer_id')

@admin.register(Load)
class LoadAdmin(admin.ModelAdmin):
    list_display = ('load_number', 'status', 'customer', 'company', 'pickup_date', 'delivery_date', 'created_at')
    list_filter = ('status', 'company', 'created_at')
    search_fields = ('load_number', 'customer')
