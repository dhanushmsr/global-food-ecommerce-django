from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
import random

# =====================================================================
# 1. USER PROFILES EXTENSION (WITH OTP SECURITY MATRIX)
# =====================================================================
class UserProfile(models.Model):
    # ✅ models.CASCADE ensures that if a User is dropped from Admin, this profile drops instantly too!
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # 🚀 UPDATED: Expanded max_length to 20 to safely contain explicit international formatting markers (+91 / +49)
    phone_number = models.CharField(max_length=20, unique=True)
    address = models.TextField()

    # Advanced Security Multi-Channel Verification Indicators
    email_verified = models.BooleanField(default=False)
    phone_verified = models.BooleanField(default=False)
    
    # Secure Volatile OTP Token Repositories
    registration_email_otp = models.CharField(max_length=6, null=True, blank=True)
    registration_phone_otp = models.CharField(max_length=6, null=True, blank=True)
    password_reset_otp = models.CharField(max_length=6, null=True, blank=True)
    otp_expiry = models.DateTimeField(null=True, blank=True)

    def generate_registration_otps(self):
        """
        Generates individual distinct 6-digit verification codes valid for 10 minutes.
        """
        self.registration_email_otp = f"{random.randint(100000, 999999)}"
        self.registration_phone_otp = f"{random.randint(100000, 999999)}"
        self.otp_expiry = timezone.now() + timezone.timedelta(minutes=10)
        self.save()

    def generate_reset_otp(self):
        """
        Generates an access recovery token valid for 5 minutes.
        """
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
# 3. PROMOTIONAL RULES (UPDATED WITH TARGETED VIP FILTERS)
# =====================================================================
class Coupon(models.Model):
    code = models.CharField(max_length=20, unique=True)
    discount_percentage = models.IntegerField(validators=[MinValueValidator(0)])
    active = models.BooleanField(default=True)
    
    specific_user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='exclusive_coupons')
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Tracks exactly who has redeemed this promo code
    used_by = models.ManyToManyField(User, blank=True, related_name='redeemed_coupons')

    def __str__(self):
        return f"{self.code} ({self.discount_percentage}%)"


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
    PAYMENT_CHOICES = [('PAYPAL', 'PayPal'), ('CARD', 'Card'), ('COD', 'COD')]
    
    STATUS_CHOICES = [
        ('PLACED', 'Received / Erhalten'), 
        ('PREPARING', 'Kitchen / In der Küche'), 
        ('OUT_FOR_DELIVERY', 'Out for Delivery / Unterwegs'),
        ('DELIVERED', 'Completed / Abgeschlossen'),
        ('CANCELLED', 'Cancelled / Storniert')
    ]
    
    TYPE_CHOICES = [
        ('DELIVERY', 'Delivery / Lieferung'),
        ('PICKUP', 'Pickup / Abholung'),
        ('DINE_IN', 'Dine-In / Vor Ort')
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    delivery_address = models.TextField(blank=True, null=True)
    
    # 🚀 UPDATED: Expanded to max_length=20 to match your profile models configuration layout safely
    phone_number = models.CharField(max_length=20)
    
    payment_method = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default='COD')
    order_type = models.CharField(max_length=15, choices=TYPE_CHOICES, default='DELIVERY') 
    
    subtotal = models.DecimalField(max_digits=10, decimal_places=2)
    gst_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00) 
    coupon_applied = models.ForeignKey(Coupon, on_delete=models.SET_NULL, null=True, blank=True)
    final_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    status = models.CharField(max_length=25, choices=STATUS_CHOICES, default='PLACED')
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