from django.db import models
from django.contrib.auth.models import User

class SavedCarrier(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    dot_number = models.CharField(max_length=20)
    mc_number = models.CharField(max_length=20)
    legal_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    saved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.legal_name} (DOT: {self.dot_number})"

class CompanyInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    company_name = models.CharField(max_length=255, default="Bullets Transport LLC")
    logo = models.ImageField(upload_to='company_logos/', null=True, blank=True)
    contact = models.CharField(max_length=255, blank=True)
    mc_scac = models.CharField(max_length=50, blank=True)
    email = models.EmailField(max_length=255, blank=True)
    address1 = models.CharField(max_length=255, blank=True)
    address2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    fax = models.CharField(max_length=20, blank=True)

    def __str__(self):
        return self.company_name
