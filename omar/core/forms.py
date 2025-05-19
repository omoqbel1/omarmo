from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import CompanyInfo, Company
import re

class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, help_text="Required. Enter a valid email address.")

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({'placeholder': 'Enter username'})
        self.fields['email'].widget.attrs.update({'placeholder': 'Enter email'})
        self.fields['password1'].widget.attrs.update({'placeholder': 'Enter password'})
        self.fields['password2'].widget.attrs.update({'placeholder': 'Confirm password'})

class CompanyInfoForm(forms.ModelForm):
    class Meta:
        model = CompanyInfo
        fields = [
            'company_name', 'logo', 'contact', 'mc_scac', 'email', 'cc_all_emails',
            'address1', 'address2', 'city', 'state', 'zip_code', 'phone', 'fax', 'carrier_terms','next_load_number'
        ]
        labels = {
            'company_name': 'Company Name',
            'logo': 'Company Logo',
            'contact': 'Contact Person',
            'mc_scac': 'MC/SCAC Number',
            'email': 'Email Address',
            'cc_all_emails': 'CC on All Emails',
            'address1': 'Address Line 1',
            'address2': 'Address Line 2',
            'city': 'City',
            'state': 'State',
            'zip_code': 'ZIP Code',
            'phone': 'Phone Number',
            'fax': 'Fax Number',
            'carrier_terms': 'Carrier Terms',
            'next_load_number': 'Next Load Number',
        }
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter company name'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'form-input'}),
            'contact': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter contact name'}),
            'mc_scac': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter MC/SCAC number'}),
            'email': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Enter email address'}),
            'cc_all_emails': forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'Enter CC email address'}),
            'address1': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter address line 1'}),
            'address2': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter address line 2'}),
            'city': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter city'}),
            'state': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter state'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter ZIP code'}),
            'phone': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter phone number'}),
            'fax': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter fax number'}),
            'carrier_terms': forms.Textarea(attrs={'class': 'form-input', 'placeholder': 'Enter carrier terms'}),
            'next_load_number': forms.NumberInput(attrs={'class': 'form-input', 'placeholder': 'Enter starting load number', 'min': '1', 'step': '1'}),
        }

    def clean_phone(self):
        phone = self.cleaned_data.get('phone')
        if phone:
            cleaned_phone = re.sub(r'[^\d]', '', phone)
            if not cleaned_phone or not cleaned_phone.isdigit() or len(cleaned_phone) < 7:
                raise forms.ValidationError("Enter a valid phone number (at least 7 digits).")
        return phone

class LoginForm(AuthenticationForm):
    company_code = forms.CharField(max_length=50, required=True, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter company code'}))
    username = forms.CharField(max_length=254, widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Enter username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Enter password'}))

    def clean_company_code(self):
        code = self.cleaned_data.get('company_code')
        if not Company.objects.filter(code__iexact=code).exists():
            raise forms.ValidationError("Invalid company code.")
        return code
