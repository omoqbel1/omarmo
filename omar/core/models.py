from django.db import models
from django.contrib.auth.models import User

def get_default_company():
    """
    Returns the default Company instance for ForeignKey fields.
    If no company exists, creates one with a default code.
    """
    try:
        # Try to get the first Company instance
        return Company.objects.first().id
    except (AttributeError, Company.DoesNotExist):
        # If no company exists, create a default one
        default_company = Company.objects.create(code="DEFAULT", is_paused=False)
        return default_company.id

class Company(models.Model):
    code = models.CharField(max_length=50, unique=True)
    is_paused = models.BooleanField(default=False)

    def __str__(self):
        return self.code

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='userprofile')
    is_approved = models.BooleanField(default=False)
    company = models.ForeignKey(Company, on_delete=models.SET_NULL, null=True, blank=True)
    is_superuser_profile = models.BooleanField(default=False)

    def __str__(self):
        return self.user.username

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

class CompanyInfo(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_info')
    company_name = models.CharField(max_length=100, blank=True)
    logo = models.ImageField(upload_to='logos/', blank=True, null=True)
    address = models.TextField(blank=True)  # Consider splitting this too in the future
    address1 = models.CharField(max_length=255, blank=True)
    address2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    next_load_number = models.IntegerField(default=1000)
    state = models.CharField(max_length=2, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    fax = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    contact = models.CharField(max_length=100, blank=True)
    mc_scac = models.CharField(max_length=50, blank=True)
    carrier_terms = models.TextField(
        blank=True,
        default=(
            "Driver can be inserted rate deliveries. The undersigned hereby acknowledges and agrees to "
            "transport the above referenced shipment, and confirms that Carrier maintains insurance "
            "coverage with a minimum of $1,000,000 general liability, $1,000,000 auto liability and "
            "$100,000 cargo liability. This Load/Rate Confirmation - Agreement must be signed and "
            "returned and faxed to us ****** BEFORE PICKUP. FAX TO NUMBER AT THE TOP OF THE PAGE ******"
        )
    )
    cc_all_emails = models.EmailField(blank=True, null=True)

    def __str__(self):
        return self.company_name or "No Company Name"

    class Meta:
        verbose_name = "Company Info"
        verbose_name_plural = "Company Info"

class SavedCarrier(models.Model):
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
        ('Dont Use', "Don't Use"),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='carriers')
    dot_number = models.CharField(max_length=50)
    mc_number = models.CharField(max_length=50)
    legal_name = models.CharField(max_length=255)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_carriers')
    saved_at = models.DateTimeField(auto_now_add=True)
    is_onboarded = models.BooleanField(default=False)
    ein_number = models.CharField(max_length=50, blank=True, null=True)
    company_officer = models.CharField(max_length=255, blank=True, null=True)
    street = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    state = models.CharField(max_length=2, blank=True, null=True)
    zip_code = models.CharField(max_length=10, blank=True, null=True)
    contact_person = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Active')
    insurance_type = models.CharField(max_length=50, blank=True, null=True)
    insurance_carrier = models.CharField(max_length=255, blank=True, null=True)
    policy_number = models.CharField(max_length=50, blank=True, null=True)
    posted_date = models.DateField(blank=True, null=True)
    coverage_from = models.CharField(max_length=50, blank=True, null=True)  # Changed to CharField for monetary values
    coverage_to = models.CharField(max_length=50, blank=True, null=True)    # Changed to CharField for monetary values
    effective_date = models.DateField(blank=True, null=True)
    cancellation_date = models.DateField(blank=True, null=True)

    def __str__(self):
        return self.legal_name

    class Meta:
        verbose_name = "Saved Carrier"
        verbose_name_plural = "Saved Carriers"

class CarrierFile(models.Model):
    carrier = models.ForeignKey(SavedCarrier, on_delete=models.CASCADE, related_name='files')
    file = models.FileField(upload_to='carrier_documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.carrier.legal_name} - {self.file.name}"

    class Meta:
        verbose_name = "Carrier File"
        verbose_name_plural = "Carrier Files"

class Customer(models.Model):
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='customers')
    customer_id = models.IntegerField(unique=True)
    company_name = models.CharField(max_length=255, blank=True)
    name = models.CharField(max_length=255)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip = models.CharField(max_length=10, blank=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} (ID: {self.customer_id})"

    class Meta:
        verbose_name = "Customer"
        verbose_name_plural = "Customers"
        unique_together = ('company', 'customer_id')

class Load(models.Model):
    STATUS_CHOICES = [
        ('ACTIVE', 'Active'),
        ('BOOKED', 'Booked'),
        ('PAID', 'Paid'),
        ('COMPLETED', 'Completed'),
        ('PROBLEM', 'Problem'),
    ]

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='loads')
    load_number = models.IntegerField(unique=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='ACTIVE')
    customer = models.CharField(max_length=255, default="Unknown Customer")
    carrier = models.CharField(max_length=255, blank=True)
    pickup_date = models.DateField(blank=True, null=True)
    pickup_appointment_time = models.CharField(max_length=5, blank=True, null=True)
    pickup_city = models.CharField(max_length=100, blank=True)
    pickup_state = models.CharField(max_length=2, blank=True)
    pickup_zip = models.CharField(max_length=10, blank=True)
    pickup_address = models.TextField(blank=True)
    pickup_name = models.CharField(max_length=255, blank=True, null=True)
    pickup_phone = models.CharField(max_length=15, blank=True, null=True)
    pickup_email = models.EmailField(blank=True, null=True)
    pickup_instructions = models.TextField(blank=True)
    pickup_internal_notes = models.TextField(blank=True)
    delivery_date = models.DateField(blank=True, null=True)
    delivery_appointment_time = models.CharField(max_length=5, blank=True, null=True)
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_state = models.CharField(max_length=2, blank=True)
    delivery_zip = models.CharField(max_length=10, blank=True)
    delivery_address = models.TextField(blank=True)
    delivery_name = models.CharField(max_length=255, blank=True, null=True)
    delivery_phone = models.CharField(max_length=15, blank=True, null=True)
    delivery_email = models.EmailField(blank=True, null=True)
    delivery_instructions = models.TextField(blank=True)
    cust_miles = models.IntegerField(default=0)
    cust_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cust_amt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    carr_miles = models.IntegerField(default=0)
    carr_rate = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    carr_amt = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    total_miles = models.IntegerField(default=0)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    driver_1 = models.CharField(max_length=255, blank=True, null=True)
    driver_1_cell = models.CharField(max_length=15, blank=True, null=True)
    driver_2 = models.CharField(max_length=255, blank=True, null=True)
    driver_2_cell = models.CharField(max_length=15, blank=True, null=True)
    truck_number = models.CharField(max_length=50, blank=True, null=True)
    trailer_number = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        return f"Load #{self.load_number}"

    class Meta:
        verbose_name = "Load"
        verbose_name_plural = "Loads"
        unique_together = ('company', 'load_number')

class Commodity(models.Model):
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name='commodities')
    type = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    weight = models.DecimalField(max_digits=10, decimal_places=1, default=0.0)
    value = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    def __str__(self):
        return f"{self.type or 'No Type'} - {self.description} (Qty: {self.quantity}, Weight: {self.weight} lbs, Value: ${self.value})"

    class Meta:
        verbose_name = "Commodity"
        verbose_name_plural = "Commodities"

class AdditionalPickup(models.Model):
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name='additional_pickups')
    name = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip = models.CharField(max_length=10, blank=True)
    date = models.DateField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    appointment_time = models.CharField(max_length=5, blank=True, null=True)
    instructions = models.TextField(blank=True)

    def __str__(self):
        return f"Additional Pickup for Load #{self.load.load_number}"

    class Meta:
        verbose_name = "Additional Pickup"
        verbose_name_plural = "Additional Pickups"

class AdditionalDelivery(models.Model):
    load = models.ForeignKey(Load, on_delete=models.CASCADE, related_name='additional_deliveries')
    name = models.CharField(max_length=255, blank=True, null=True)
    address = models.TextField(blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=2, blank=True)
    zip = models.CharField(max_length=10, blank=True)
    date = models.DateField(blank=True, null=True)
    phone = models.CharField(max_length=15, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    appointment_time = models.CharField(max_length=5, blank=True, null=True)
    instructions = models.TextField(blank=True)

    def __str__(self):
        return f"Additional Delivery for Load #{self.load.load_number}"

    class Meta:
        verbose_name = "Additional Delivery"
        verbose_name_plural = "Additional Deliveries"

class InsuranceScrapeJob(models.Model):
    carrier = models.ForeignKey(SavedCarrier, on_delete=models.CASCADE, related_name='insurance_scrape_jobs')
    mc_number = models.CharField(max_length=50)
    status = models.CharField(max_length=50, choices=[
        ('PENDING', 'Pending'),
        ('CAPTCHA_SOLVING', 'Solving CAPTCHA'),
        ('PROCESSING', 'Processing'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed')
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    result_data = models.JSONField(null=True, blank=True)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"Insurance scrape for {self.mc_number} - {self.status}"
