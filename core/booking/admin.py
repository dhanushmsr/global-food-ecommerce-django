from django.contrib import admin
from .models import UserProfile, FoodCategory, FoodItem, Coupon, CartItem, OrderSummary, OrderBreakdownItem

# Register the Guest Profile Extension
admin.site.register(UserProfile)
admin.site.register(CartItem)
admin.site.register(FoodCategory)

@admin.register(FoodItem)
class FoodItemAdmin(admin.ModelAdmin):
    # Updated old 'name' field to 'name_de' and 'name_en' plus added 'item_type' for German VAT
    list_display = ('name_de', 'name_en', 'category', 'price', 'item_type', 'diet_type', 'is_available')
    list_filter = ('category', 'item_type', 'diet_type', 'is_available')
    search_fields = ('name_de', 'name_en')

@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ('code', 'discount_percentage', 'active')
    list_filter = ('active',)

# Inline display so you can view breakdown food items directly inside the main summary block
class OrderBreakdownInline(admin.TabularInline):
    model = OrderBreakdownItem
    extra = 0

@admin.register(OrderSummary)
class OrderSummaryAdmin(admin.ModelAdmin):
    # Added 'order_type' to track Delivery vs. Pickup vs. Dine-in in the overview
    list_display = ('id', 'user', 'order_type', 'payment_method', 'subtotal', 'gst_amount', 'final_amount', 'status', 'estimated_time', 'created_at')
    list_filter = ('status', 'order_type', 'payment_method', 'created_at')
    inlines = [OrderBreakdownInline]