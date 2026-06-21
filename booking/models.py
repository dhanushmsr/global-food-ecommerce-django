from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
import random

# =====================================================================
# 1. USER PROFILES EXTENSION (WITH OTP SECURITY MATRIX)
# =====================================================================
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone_number = models.CharField(max_length=20, unique=True)
    address = models.TextField()

    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    
    registration_email_otp = models.CharField(max_length=6, null=True, blank=True)
    registration_phone_otp = models.CharField(max_length=6, null=True, blank=True)
    password_reset_otp = models.CharField(max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)

    def generate_registration_otps(self):
        self.registration_email_otp = f"{random.randint(100000, 999999)}"
        self.registration_phone_otp = f"{random.randint(100000, 999999)}"
        self.otp_expiry = timezone.now() + timezone.timedelta(minutes=10)
        self.save()

    def generate_reset_otp(self):
        self.password_reset_otp = f"{random.randint(100000, 999999)}"
        self.otp_expiry = timezone.now() + timezone.timedelta(minutes=5)
        self.save()

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.phone_number})"


# =====================================================================
# 2. MENU & STRUCTURAL TAX INVENTORY LAYOUTS
# =====================================================================
class FoodCategory(models.Model):
    name_en = models.CharField(max_length=50, unique=True, help_text="e.g., Starters")
    name_de = models.CharField(max_length=50, unique=True, help_text="e.g., Vorspeisen")

    def __str__(self):
        return f"{self.name_en} / {self.name_de}"


class FoodItem(models.Model):
    DIET_CHOICES = [
        ('VEG', 'Veg 🟢'),
        ('NON_VEG', 'Non-Veg 🔴'),
    ]
    
    ITEM_TYPE_CHOICES = [
        ('FOOD', 'Food / Speise (7% VAT)'),
        ('BEVERAGE', 'Beverage / Getränk (19% VAT)'),
    ]

    category = models.ForeignKey(FoodCategory, on_delete=models.CASCADE, related_name='items')
    name_en = models.CharField(max_length=100)
    name_de = models.CharField(max_length=100)
    description_en = models.TextField(blank=True)
    description_de = models.TextField(blank=True)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    image = models.ImageField(upload_to='dishes/', blank=True, null=True)
    diet_type = models.CharField(max_length=10, choices=DIET_CHOICES, default='VEG')
    item_type = models.CharField(max_length=15, choices=ITEM_TYPE_CHOICES, default='FOOD') 
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name_en} - €{self.price}"


# =====================================================================
# 3. PROMOTIONAL RULES
# =====================================================================
class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_percentage = models.IntegerField(validators=[MinValueValidator(0)])
    active = models.BooleanField(default=True)
    
    specific_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='exclusive_coupons')
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    applicable_category = models.ForeignKey(FoodCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name='linked_coupons')
    used_by = models.ManyToManyField(User, blank=True, related_name='redeemed_coupons')

    def __str__(self):
        if self.applicable_category:
            return f"{self.code} ({self.discount_percentage}% OFF - {self.applicable_category.name_en})"
        return f"{self.code} ({self.discount_percentage}% OFF - Global)"


# =====================================================================
# 4. CART INTERACTIONS
# =====================================================================
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cart_items')
    food_item = models.ForeignKey(FoodItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.quantity}x {self.food_item.name_en} ({self.user.username})"


# =====================================================================
# 5. BUSINESS ANALYTICS & LOGISTICS TRACKING
# =====================================================================
class OrderSummary(models.Model):
    PAYMENT_CHOICES = [
        ('PAYPAL', 'PayPal'), 
        ('CARD', 'Card'), 
        ('COD', 'COD'),
        ('MOLLIE', 'Mollie Gateway')
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('Pending', 'Pending / Ausstehend'),
        ('Paid', 'Paid / Erfolgreich gezahlt'),
        ('Cancelled', 'Cancelled / Storniert'),
        ('Failed', 'Failed / Fehlgeschlagen')
    ]
    
    STATUS_CHOICES = [
        ('verifying', 'Verifying / System-Validierung'),
        ('processing', 'Processing / In Bearbeitung'),
        ('failed', 'Payment Failed / Fehlgeschlagen'),
        ('success', 'Payment Success / Erfolgreich'),
        
        ('ordered', 'Ordered / Received / Erhalten'), 
        ('preparing', 'Kitchen / Preparing / In der Küche'), 
        ('delivered', 'Out for Delivery / Unterwegs'),
        ('completed', 'Completed / Abgeschlossen'),
        ('cancelled', 'Cancelled / Storniert')
    ]
    
    TYPE_CHOICES = [
        ('DELIVERY', 'Delivery / Lieferung'),
        ('PICKUP', 'Pickup / Abholung'),
        ('DINE_IN', 'Dine-In / Vor Ort')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    delivery_address = models.TextField(blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='COD')
    order_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='DELIVERY') 
    payment_status = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES, default='Pending')
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    coupon_applied = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='verifying')
    is_notified = models.BooleanField(default=False)
    
    estimated_time = models.CharField(max_length=50, default="Pending Manager Allocation") 
    created_at = models.DateTimeField(auto_now_add=True)
    
    canceled_by = models.CharField(max_length=20, null=True, blank=True, choices=[
        ('CUSTOMER', 'Customer'),
        ('OWNER', 'Owner / Staff')
    ])

    def __str__(self):
        return f"Order #{self.id} - €{self.final_amount} ({self.status})"


class OrderBreakdownItem(models.Model):
    order = models.ForeignKey(OrderSummary, on_delete=models.CASCADE, related_name='items')
    food_item_name = models.CharField(max_length=120)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=8, decimal_places=2)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.quantity}x {self.food_item_name} for Order #{self.order.id}"


# =====================================================================
# 6. DYNAMIC OWNER ADVERTISING & PROMO REGISTRY (FIFO STRICT LIMIT 4)
# =====================================================================
class PromoAnnouncement(models.Model):
    image = models.ImageField(upload_to='promos/', blank=True, null=True)
    video = models.FileField(upload_to='promos/', blank=True, null=True)
    
    notes_en = models.TextField(blank=True, null=True, help_text="Announcement description notes in English")
    notes_de = models.TextField(blank=True, null=True, help_text="Ankündigungstext auf Deutsch")
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def save(self, *args, **kwargs):
        # 🎯 STRICT FIFO ENFORCEMENT: Auto-deletes oldest item if total count hits 4
        max_allowed = 4
        current_count = PromoAnnouncement.objects.count()
        
        if not self.pk and current_count >= max_allowed:
            excess_items = PromoAnnouncement.objects.order_by('created_at')[:(current_count - max_allowed + 1)]
            for item in excess_items:
                if item.image:
                    item.image.delete(save=False)
                if item.video:
                    item.video.delete(save=False)
                item.delete()
                
        super(PromoAnnouncement, self).save(*args, **kwargs)

    def __str__(self):
        return f"Promo Announcement #{self.id} - Uploaded at {self.created_at.strftime('%d.%m.%Y %H:%M')}"