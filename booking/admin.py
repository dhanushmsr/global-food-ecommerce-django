from django.contrib import admin
from .models import UserProfile, FoodCategory, FoodItem, Coupon, CartItem, OrderSummary, OrderBreakdownItem

# =====================================================================
# 1. BASIC MODELS CONFIGURATION (Standard Registrations)
# =====================================================================
admin.site.register(UserProfile)
admin.site.register(CartItem)
admin.site.register(FoodCategory)


# =====================================================================
# 2. ADVANCED MENU MANAGEMENT
# =====================================================================
@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    """
    Displays menu inventory. Organizes columns by German/English names,
    pricing matrix, availability flags, and specific tax rules (7% vs 19% VAT).
    """
    list_display = ('id', 'name_de', 'name_en', 'category', 'price', 'item_type', 'diet_type', 'is_available')
    list_filter = ('category', 'item_type', 'diet_type', 'is_available')
    search_fields = ('name_de', 'name_en')
    list_editable = ('price', 'is_available') # Allows quick updates directly from the main list view


# =====================================================================
# 3. PROMOTIONAL RULES CONTROL
# =====================================================================
@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    """
    Tracks promotional rules, discount metrics, and active states.
    """
    list_display = ('code', 'discount_percentage', 'active', 'min_order_amount')
    list_filter = ('active', 'created_at' if hasattr(Coupon, 'created_at') else 'active')
    search_fields = ('code',)


# =====================================================================
# 4. ORDER FULFILLMENT & WEB GATEWAY LOGISTICS (Command Center)
# =====================================================================
class OrderBreakdownInline(admin.TabularInline):
    """
    Embeds the detailed items list directly inside the parent Order summary page.
    This saves your staff from clicking into separate files to see what food to make.
    """
    model = OrderBreakdownItem
    extra = 0
    readonly_fields = ('food_item_name', 'quantity', 'unit_price', 'total_price')


@admin.register(OrderSummary)
class OrderSummaryAdmin(admin.ModelAdmin):
    """
    The heart of your dashboard operations. Displays delivery types, online vs cod 
    payment methods, Mollie statuses, and overall preparation trackers.
    """
    list_display = (
        'id', 
        'user', 
        'order_type',       # 🚀 Added: Delivery / Pickup / Dine-In
        'payment_method',   # 🚀 Added: PAYPAL / CARD / COD / MOLLIE
        'payment_status',   # 🚀 Added: Pending / Paid / Cancelled / Failed
        'subtotal', 
        'gst_amount', 
        'final_amount', 
        'status',          # PLACED / PREPARING / OUT_FOR_DELIVERY / DELIVERED
        'estimated_time', 
        'created_at'
    )
    
    # Left sidebar filters for speedy order segregation
    list_filter = ('status', 'order_type', 'payment_method', 'payment_status', 'created_at')
    
    # Search bar parameters to instantly pull orders by ID or customer name
    search_fields = ('id', 'user__username', 'phone_number')
    
    # Inlines inject your row-by-row food breakdown layout
    inlines = [OrderBreakdownInline]