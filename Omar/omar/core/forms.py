from django import forms
from .models import CompanyInfo

class CompanyInfoForm(forms.ModelForm):
    class Meta:
        model = CompanyInfo
        fields = ['company_name', 'logo', 'contact', 'mc_scac', 'email', 'address1', 'address2', 'city', 'state', 'zip_code', 'phone', 'fax']
