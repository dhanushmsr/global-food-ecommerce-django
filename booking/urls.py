from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # 🌍 Ganesha Public Landing/Intro Page & Multi-language Toggles
    path('', views.welcome_index, name='welcome'),
    path('menu/', views.home, name='home'),
    path('set-language/', views.set_language, name='set_language'),
    
    # 🔑 Guest Authentication Core Pathways & Phone Verification Matrix
    path('register/', views.register_user, name='register'),
    # Note: verify_registration has been removed!
    path('login/', views.login_user, name='login'),
    path('logout/', views.logout_user, name='logout'),
    
    # 🔒 Real-Time Password Accessibility Lifeline Recovery
    path('login/forgot-password/', views.forgot_password_request, name='forgot_password'),
    path('login/forgot-password/verify/', views.forgot_password_verify, name='forgot_password_verify'),
    
    # 🍲 Menu, Category & Voucher Inventory Management (Staff Side)
    path('menu/add/', views.add_modify_menu, name='add_modify_menu'),
    path('menu/edit/<int:item_id>/', views.add_modify_menu, name='add_modify_menu'),
    
    # 📁 Category Workspace Management
    path('category/add/', views.add_category_frontend, name='add_category_frontend'), 
    path('category/edit/<int:cat_id>/', views.add_category_frontend, name='edit_category_frontend'), 
    
    # 🎫 Voucher Control Management
    path('coupon/add/', views.add_coupon_frontend, name='add_coupon_frontend'),      
    
    # 🛒 Cart Ecosystem & Checkout Engines
    path('cart/add/<int:item_id>/', views.add_to_cart, name='add_to_cart'),
    path('cart/view/', views.view_cart, name='view_cart'),
    path('cart/update/<int:item_id>/', views.update_cart_quantity, name='update_cart_quantity'),
    
    # 💳 Mollie Payment Gateway Integration Channels (UPDATED FOR PRODUCTION)
    path('payment/checkout/<int:order_id>/', views.initiate_mollie_payment, name='payment_checkout'),
    path('payment/success/<int:order_id>/', views.payment_success_view, name='payment_success'),
    path('payment/cancel/<int:order_id>/', views.payment_cancel_view, name='payment_cancel'),
    path('payment/webhook/', views.mollie_webhook_view, name='payment_webhook'),
    
    # 📋 Business Command Desks, Tracking History Logs & Reorder Engines
    path('dashboard/', views.dashboard, name='dashboard'),
    path('bill/<int:order_id>/', views.view_bill, name='view_bill'),
    path('order/<int:order_id>/reorder/', views.reorder_past_items, name='reorder_past_items'),
    
    # 🤖 Isolated Administrative Portal Sub-modules
    path('owner/dashboard/', views.hotel_owner_dashboard, name='hotel_management'),
    path('owner/todays-orders/', views.owner_todays_orders, name='owner_todays_orders'),
    path('owner/order-history/', views.owner_order_history, name='owner_order_history'),
    path('owner/user-details/', views.owner_user_details, name='owner_user_details'),
    path('owner/order/<int:order_id>/update/', views.update_order_logistics, name='update_order_logistics'),
    path('owner/order/<int:order_id>/delete/', views.delete_order_history, name='delete_order_history'),
    
    # 🌐 Background Automation Watchdog APIs
    path('api/check-orders/', views.check_new_orders_api, name='check_new_orders_api'),
    path('api/reverse-geocode/', views.reverse_geocode_address, name='reverse_geocode_address'),
    
    # 🚀 CONNECTED: Processes both the GET template view and the POST payload validation for cancellation parameters cleanly
    path('order/<int:order_id>/cancel/', views.cancel_order, name='cancel_order'),
    
    # 👤 Secure Profile Lifecycle Gate Pathways
    path('profile/update/', views.update_profile, name='update_profile'),
    # Note: verify_profile_update has been removed!
    path('terms/', views.terms_conditions, name='terms_conditions'),
    path('delete-profile/', views.delete_profile, name='delete_profile'),
]

# Map media folders for dynamically uploaded food images
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)