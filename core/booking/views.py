from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.conf import settings
from django.core.mail import send_mail # Live SMTP Mail Transfer Engine
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils import timezone
from django.utils.timezone import localtime # 🚀 CRITICAL TIMEZONE LOCALIZATION HOOK
from django.db import models          # Injects models namespace for Q objects
from django.db.models import Sum, Count
from .models import FoodCategory, FoodItem, Coupon, CartItem, OrderSummary, OrderBreakdownItem, UserProfile
from decimal import Decimal
import requests                        # Required for live OpenStreetMap reverse-geocoding API lookups
from twilio.rest import Client          # Live Virtual Cellular API SDK
from django.core.mail import EmailMessage # Injects robust HTML message packaging engines
from django.template.loader import render_to_string # Injects compile layout parser utilities
import threading # Runs email delivery on a background thread so the UI never freezes

# =====================================================================
# LIVE NETWORK DISPATCH UTILITY INFRASTRUCTURE
# =====================================================================
def send_live_sms_gateway(to_number, otp_code):
    """
    Routes real-time verification codes over active mobile cellular networks via Twilio.
    Bypasses gracefully to terminal logs if credentials are unassigned.
    """
    try:
        if hasattr(settings, 'TWILIO_ACCOUNT_SID') and settings.TWILIO_ACCOUNT_SID and not settings.TWILIO_ACCOUNT_SID.startswith('ACxxx'):
            client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
            client.messages.create(
                body=f"Ganesha Safe Code: {otp_code}. Valid for 10 minutes. Please do not share this token.",
                from_=settings.TWILIO_PHONE_NUMBER,
                to=to_number
            )
            print(f"📱 [NETWORK SUCCESS] Real-time cellular SMS routed to {to_number}")
        else:
            print(f"\n📱 [SETTINGS WARNING] Twilio unconfigured. Phone OTP text for {to_number}: {otp_code}\n")
    except Exception as e:
        print(f"⚠️ Live cellular SMS network routing failure alert log: {e}")


# =====================================================================
# 1. MULTILINGUAL SYSTEM TOGGLE
# =====================================================================
def set_language(request):
    """
    Toggles the user's preferred language between English ('en') and German ('de')
    and saves it inside the browser session.
    """
    lang = request.GET.get('lang', 'de')
    request.session['lang'] = lang
    return redirect(request.META.get('HTTP_REFERER', 'home'))


# =====================================================================
# 2. GUEST AUTHENTICATION & MULTI-CHANNEL LIVE OTP SIGN-UP
# =====================================================================
def register_user(request):
    error = None
    if request.method == 'POST':
        country_code = request.POST.get('country_code', '+49').strip()
        phone_raw = request.POST.get('phone_raw', '').strip()
        email = request.POST.get('email')
        password = request.POST.get('password')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        address = request.POST.get('address')
        
        # 🚀 Strips accidental leading zero input errors out dynamically
        if phone_raw.startswith('0'):
            phone_raw = phone_raw[1:]
            
        # Compile country prefix elements with the raw mobile digits cleanly
        phone = country_code + phone_raw
        
        if User.objects.filter(username=phone).exists():
            error = "This phone number is already registered. / Diese Nummer ist bereits registriert."
        elif User.objects.filter(email=email).exists():
            error = "This email is already registered. / Diese E-Mail ist bereits registriert."
        else:
            user = User.objects.create_user(
                username=phone, 
                email=email,
                password=password,
                first_name=first_name, 
                last_name=last_name
            )
            profile = UserProfile.objects.create(user=user, phone_number=phone, address=address)
            profile.generate_registration_otps()
            
            # 🚀 CHANNEL A: REAL-TIME GMAIL SMTP NETWORK DISPATCH
            email_subject = "Ganesha Portal - Identity Verification Action Required"
            email_body = f"Namaste {first_name},\n\nThank you for registering at Ganesha! To activate your digital profile, use the verification key below:\n\nVerification Code: {profile.registration_email_otp}\n\nThis token is valid for 10 minutes."
            
            try:
                send_mail(
                    subject=email_subject,
                    message=email_body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@ganesha.com'),
                    recipient_list=[email],
                    fail_silently=False,
                )
                print(f"📧 [NETWORK SUCCESS] Real-time SMTP transmission routed to {email}")
            except Exception as e:
                print(f"\n📧 [SETTINGS WARNING] SMTP Server failure. Email registration code for {email}: {profile.registration_email_otp}\nDetail: {e}")
            
            # 🚀 CHANNEL B: REAL-TIME SMS SMART ROUTING VIA CELLULAR API
            send_live_sms_gateway(phone, profile.registration_phone_otp)
            
            request.session['pending_verification_user_id'] = user.id
            return redirect('verify_registration')
            
    return render(request, 'booking/register.html', {'error': error})


def verify_registration(request):
    user_id = request.session.get('pending_verification_user_id')
    if not user_id:
        return redirect('register')
        
    user = get_object_or_404(User, id=user_id)
    profile = user.profile
    error = None
    
    if request.method == 'POST':
        email_otp = request.POST.get('email_otp')
        phone_otp = request.POST.get('phone_otp')
        
        if timezone.now() > profile.otp_expiry:
            error = "Verification codes have expired. Please sign up again. / OTP abgelaufen."
        elif profile.registration_email_otp == email_otp and profile.registration_phone_otp == phone_otp:
            profile.email_verified = True
            profile.phone_verified = True
            profile.registration_email_otp = None
            profile.registration_phone_otp = None
            profile.save()
            
            login(request, user)
            del request.session['pending_verification_user_id']
            return redirect('home')
        else:
            error = "Invalid combination of verification codes. / Ungültiger OTP-Code."
            
    return render(request, 'booking/verify_registration.html', {'error': error})


def login_user(request):
    error = None
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        
        # 🚀 FIX: If it's a plain word (like 'admin'), bypass country code formatting!
        if phone and not phone.startswith('+'):
            if phone.isalpha():
                # Keeps the raw text intact for superuser login handles
                pass
            elif phone.startswith('0'):
                phone = '+49' + phone[1:]
            elif len(phone) == 10 and phone[0] in ['6', '7', '8', '9']:
                phone = '+91' + phone
            else:
                phone = '+49' + phone

        user = authenticate(request, username=phone, password=request.POST.get('password'))
        if user:
            login(request, user)
            return redirect('home')
        error = "Invalid credentials. / Ungültige Anmeldedaten."
    return render(request, 'booking/login.html', {'error': error})


def logout_user(request):
    logout(request)
    return redirect('welcome')


# =====================================================================
# REAL-TIME PASSWORD ACCESSIBILITY LIFELINE CONTROL
# =====================================================================
def forgot_password_request(request):
    error = None
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        if phone and not phone.startswith('+'):
            if phone.startswith('0'):
                phone = '+49' + phone[1:]
            elif len(phone) == 10 and phone[0] in ['6', '7', '8', '9']:
                phone = '+91' + phone
            else:
                phone = '+49' + phone

        profile = UserProfile.objects.filter(phone_number=phone).first()
        
        if profile:
            profile.generate_reset_otp()
            send_live_sms_gateway(phone, profile.password_reset_otp)
            request.session['reset_password_phone'] = phone
            return redirect('forgot_password_verify')
        else:
            error = "Phone record not identified in database. / Nummer nicht gefunden."
            
    return render(request, 'booking/forgot_password_request.html', {'error': error})


def forgot_password_verify(request):
    phone = request.session.get('reset_password_phone')
    if not phone:
        return redirect('login')
        
    profile = get_object_or_404(UserProfile, phone_number=phone)
    error = None
    
    if request.method == 'POST':
        otp = request.POST.get('otp')
        new_password = request.POST.get('new_password')
        
        if timezone.now() > profile.otp_expiry:
            error = "Session code window expired. Please re-verify. / Link abgelaufen."
        elif profile.password_reset_otp == otp:
            user = profile.user
            user.set_password(new_password)
            user.save()
            
            profile.password_reset_otp = None
            profile.save()
            
            del request.session['reset_password_phone']
            return redirect('login')
        else:
            error = "Incorrect single-use token provided. / Falscher OTP-Code."
            
    return render(request, 'booking/forgot_password_verify.html', {'error': error})


# =====================================================================
# 3. PUBLIC STOREFRONT / HOME CATALOG
# =====================================================================
@login_required(login_url='login')
def home(request):
    """
    Renders the dynamic menu organized by category using the active language preference.
    """
    lang = request.session.get('lang', 'de')
    categories = FoodCategory.objects.all()
    menu_items = FoodItem.objects.filter(is_available=True)
    return render(request, 'booking/home.html', {
        'categories': categories, 
        'menu_items': menu_items,
        'lang': lang
    })


# =====================================================================
# 4. FRONTEND CONTENT & INVENTORY MANAGEMENT (STAFF ONLY)
# =====================================================================
@user_passes_test(lambda u: u.is_staff)
def add_modify_menu(request, item_id=None):
    """
    Handles both creation and real-time updates of dishes entirely via 
    asynchronous modal submission, completely eliminating the standalone form page.
    """
    item = get_object_or_404(FoodItem, id=item_id) if item_id else None
    
    if request.method == 'POST':
        category_id = request.POST.get('category')
        if not category_id:
            default_cat, _ = FoodCategory.objects.get_or_create(
                name_de="Allgemein", 
                name_en="General"
            )
            category_id = default_cat.id
            
        name_en = request.POST.get('name_en')
        name_de = request.POST.get('name_de')
        desc_en = request.POST.get('description_en', '')
        desc_de = request.POST.get('description_de', '')
        price = request.POST.get('price')
        diet_type = request.POST.get('diet_type')
        item_type = request.POST.get('item_type', 'FOOD') 
        image_file = request.FILES.get('image')
        
        if item:
            item.category_id = category_id
            item.name_en = name_en
            item.name_de = name_de
            item.description_en = desc_en
            item.description_de = desc_de
            item.price = price
            item.diet_type = diet_type
            item.item_type = item_type
            if image_file:
                item.image = image_file
            item.save()
        else:
            FoodItem.objects.create(
                category_id=category_id, name_en=name_en, name_de=name_de,
                description_en=desc_en, description_de=desc_de, price=price,
                diet_type=diet_type, item_type=item_type, image=image_file
            )
            
    return redirect('hotel_management')


@user_passes_test(lambda u: u.is_staff)
def add_category_frontend(request):
    """
    Safely creates or fetches menu category configurations instantly from the home page forms
    without crashing on duplicate UNIQUE constraint rules.
    """
    if request.method == 'POST':
        name_en = request.POST.get('name_en', '').strip()
        name_de = request.POST.get('name_de', '').strip()
        
        if name_en and name_de:
            category, created = FoodCategory.objects.get_or_create(
                name_en=name_en,
                defaults={'name_de': name_de}
            )
            if not created and category.name_de != name_de:
                category.name_de = name_de
                category.save()
                
    return redirect('hotel_management')


@user_passes_test(lambda u: u.is_staff)
def add_coupon_frontend(request):
    """
    Safely generates promotional corporate voucher rules from the owner portal space
    including personalized user filtering assignments and min bound parameters.
    """
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        discount = request.POST.get('discount_percentage')
        user_id = request.POST.get('specific_user_id')
        min_order = request.POST.get('min_order_amount', '0.00')
        
        if code and discount:
            specific_user = User.objects.filter(id=user_id).first() if user_id else None
            
            coupon, created = Coupon.objects.get_or_create(
                code=code,
                defaults={
                    'discount_percentage': int(discount),
                    'specific_user': specific_user,
                    'min_order_amount': Decimal(min_order)
                }
            )
            if not created:
                coupon.discount_percentage = int(discount)
                coupon.specific_user = specific_user
                coupon.min_order_amount = Decimal(min_order)
                coupon.save()
                
    return redirect('hotel_management')


# =====================================================================
# 5. CART ECOSYSTEM & SPLIT GERMAN VAT CHECKOUT ENGINE
# =====================================================================
@login_required
def add_to_cart(request, item_id):
    food_item = get_object_or_404(FoodItem, id=item_id)
    cart_item, created = CartItem.objects.get_or_create(user=request.user, food_item=food_item)
    if not created:
        cart_item.quantity += 1
        cart_item.save()
    return redirect('view_cart')


@login_required
def view_cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    
    subtotal = Decimal('0.00')
    for item in cart_items:
        subtotal += item.food_item.price * item.quantity

    coupon_code = request.GET.get('coupon', '').strip()
    discount = Decimal('0.00')
    coupon_obj = None
    coupon_error = None
    
    # 1. EVALUATE PROMOTIONAL DISCOUNT RULES AND ONE-TIME EXPIRY LIMITS
    if coupon_code:
        coupon_match = Coupon.objects.filter(code__iexact=coupon_code, active=True).first()
        if coupon_match:
            if coupon_match.used_by.filter(id=request.user.id).exists():
                coupon_error = "You have already redeemed this voucher code. / Bereits eingelöst."
            elif coupon_match.specific_user and coupon_match.specific_user != request.user:
                coupon_error = "This voucher is restricted to another user profile. / Nicht zulässig."
            elif subtotal < coupon_match.min_order_amount:
                coupon_error = f"Minimum subtotal required for this promotion is €{coupon_match.min_order_amount}."
            else:
                coupon_obj = coupon_match
                discount = (subtotal * Decimal(coupon_match.discount_percentage)) / Decimal(100)
        else:
            coupon_error = "Invalid or expired voucher code. / Ungültiger Gutschein."

    # 2. COMPUTE SYSTEMATIC RATIO FOR ACCURATE TAX SUBTRACTION
    discount_ratio = Decimal('1.00')
    if subtotal > 0:
        discount_ratio = (subtotal - discount) / subtotal

    # 3. CALCULATE GERMAN SPLIT VAT BASED ON POST-DISCOUNTED REAL VALUE
    total_vat_7 = Decimal('0.00')
    total_vat_19 = Decimal('0.00')
    
    for item in cart_items:
        discounted_line_total = (item.food_item.price * item.quantity) * discount_ratio
        
        if hasattr(item.food_item, 'item_type') and item.food_item.item_type == 'BEVERAGE':
            total_vat_19 += discounted_line_total * Decimal('0.19') 
        else:
            total_vat_7 += discounted_line_total * Decimal('0.07')   

    combined_tax = total_vat_7 + total_vat_19
    final_amount = (subtotal - discount) + combined_tax
    
    profile = request.user.profile
    exclusive_offers = Coupon.objects.filter(specific_user=request.user, active=True).exclude(used_by=request.user)

    # 4. ORDER FINALIZATION SUBMISSION FORM (POST)
    if request.method == 'POST':
        if not cart_items.exists():
            return redirect('home')
            
        chosen_type = request.POST.get('order_type', 'DELIVERY')
        fallback_address = request.POST.get('address', 'Selected Option: ' + chosen_type)
        
        if coupon_obj and coupon_obj.used_by.filter(id=request.user.id).exists():
            return redirect('view_cart')
            
        order = OrderSummary.objects.create(
            user=request.user, 
            delivery_address=fallback_address if chosen_type == 'DELIVERY' else "Fulfillment Mode: " + chosen_type,
            phone_number=request.POST.get('phone'), 
            payment_method=request.POST.get('payment_method'),
            order_type=chosen_type,
            subtotal=subtotal, 
            gst_amount=combined_tax.quantize(Decimal('0.01')),
            final_amount=final_amount.quantize(Decimal('0.01')),
            coupon_applied=coupon_obj
        )
        
        if coupon_obj:
            coupon_obj.used_by.add(request.user)
            if coupon_obj.specific_user:
                coupon_obj.active = False
                coupon_obj.save()
        
        for item in cart_items:
            lang = request.session.get('lang', 'de')
            item_name = item.food_item.name_de if lang == 'de' else item.food_item.name_en
            
            OrderBreakdownItem.objects.create(
                order=order, 
                food_item_name=item_name, 
                quantity=item.quantity,
                unit_price=item.food_item.price, 
                total_price=item.food_item.price * item.quantity
            )
        
        # =====================================================================
        # 🚀 BACKGROUND THREAD ASYNCHRONOUS EMAIL DISPATCHER
        # =====================================================================
        if request.user.email:
            def send_async_email(current_order, user_email):
                try:
                    html_content = render_to_string('booking/email_receipt.html', {'order': current_order})
                    
                    email_msg = EmailMessage(
                        subject=f"Ganesha Restaurant - Bestätigung / Order Receipt #{current_order.id}",
                        body=html_content,
                        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@ganesha.com'),
                        to=[user_email]
                    )
                    email_msg.content_subtype = "html"
                    email_msg.send(fail_silently=False)
                    print(f"📧 [EMAIL SUCCESS] HTML receipt sent to background worker for {user_email}")
                except Exception as mail_err:
                    print(f"⚠️ Asynchronous checkout receipt delivery execution drop encountered: {mail_err}")

            threading.Thread(target=send_async_email, args=(order, request.user.email)).start()
        # =====================================================================
        
        cart_items.delete()
        return redirect('view_bill', order_id=order.id)

    return render(request, 'booking/cart.html', {
        'cart_items': cart_items, 
        'subtotal': subtotal, 
        'discount': discount,
        'total_vat_7': total_vat_7.quantize(Decimal('0.01')),
        'total_vat_19': total_vat_19.quantize(Decimal('0.01')),
        'final_amount': final_amount.quantize(Decimal('0.01')), 
        'coupon_obj': coupon_obj, 
        'coupon_error': coupon_error, 
        'profile': profile,
        'exclusive_offers': exclusive_offers
    })


# =====================================================================
# 6. DIGITAL INVOICES & REVENUE TRACKING LOGS
# =====================================================================
@login_required
def view_bill(request, order_id):
    order = get_object_or_404(OrderSummary, id=order_id)
    if not request.user.is_staff and order.user != request.user:
        return redirect('home')
    return render(request, 'booking/bill_invoice.html', {'order': order})


@login_required
def dashboard(request):
    orders = OrderSummary.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'booking/dashboard.html', {'orders': orders})


# =====================================================================
# 7. BUSINESS DASHBOARD & ADMINISTRATIVE PARAMETERS (OWNER PORTAL)
# =====================================================================
@user_passes_test(lambda u: u.is_staff)
def hotel_owner_dashboard(request):
    """
    Central Cockpit Panel Dashboard for Ganesha.
    Filters out completed or cancelled orders from the live active tracking queue.
    """
    now = timezone.now()
    
    active_orders = OrderSummary.objects.filter(status__in=['PLACED', 'PREPARING', 'OUT_FOR_DELIVERY'])
    for order in active_orders:
        elapsed_minutes = (now - order.created_at).total_seconds() / 60.0
        
        if order.status == 'PLACED' and elapsed_minutes >= 2:
            order.status = 'PREPARING'
            order.estimated_time = "30-40 Mins"
            order.save()
        elif order.status == 'PREPARING' and elapsed_minutes >= 25:
            order.status = 'OUT_FOR_DELIVERY'
            order.estimated_time = "10-20 Mins"
            order.save()
        elif order.status == 'OUT_FOR_DELIVERY' and elapsed_minutes >= 45:
            order.status = 'DELIVERED'
            order.estimated_time = "Ready / Bereit"
            order.save()

    all_orders = OrderSummary.objects.all().order_by('-created_at')
    active_queue_orders = all_orders.exclude(status__in=['DELIVERED', 'CANCELLED']).prefetch_related('items')
    
    all_users = UserProfile.objects.all().select_related('user')
    all_menu_items = FoodItem.objects.all().select_related('category')
    all_categories = FoodCategory.objects.all() 
    
    today_local = localtime(now).date()
    todays_orders = all_orders.filter(created_at__date=today_local)
    
    raw_todays_revenue = todays_orders.exclude(status='CANCELLED').aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0.00')
    todays_revenue = Decimal(raw_todays_revenue).quantize(Decimal('0.01'))
    todays_orders_count = todays_orders.filter(status__in=['PLACED', 'PREPARING', 'OUT_FOR_DELIVERY', 'DELIVERED']).count()
    
    raw_grand_revenue = all_orders.exclude(status='CANCELLED').aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0.00')
    grand_total_revenue = Decimal(raw_grand_revenue).quantize(Decimal('0.01'))

    return render(request, 'booking/hotel_management.html', {
        'orders': active_queue_orders,
        'users': all_users,
        'menu_items': all_menu_items,
        'categories': all_categories, 
        'todays_revenue': todays_revenue,
        'todays_count': todays_orders_count,
        'grand_total_revenue': grand_total_revenue,
    })


@user_passes_test(lambda u: u.is_staff)
def update_order_logistics(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(OrderSummary, id=order_id)
        new_status = request.POST.get('status', 'PREPARING')
        
        order.estimated_time = request.POST.get('estimated_time', '40-45 Mins')
        order.status = new_status
        
        if new_status == 'CANCELLED':
            order.canceled_by = 'OWNER'  # Logs that staff canceled it
            
        order.save()
    return redirect(request.META.get('HTTP_REFERER', 'hotel_management'))


def check_new_orders_api(request):
    """
    Background API watchdog endpoint. Scans for incoming orders and handles
    live queue-dropping interface reloads when statuses change.
    """
    now = timezone.now()
    active_orders = OrderSummary.objects.filter(status__in=['PLACED', 'PREPARING', 'OUT_FOR_DELIVERY'])
    has_status_shifted = False
    
    for order in active_orders:
        old_status = order.status
        elapsed_minutes = (now - order.created_at).total_seconds() / 60.0
        
        if order.status == 'PLACED' and elapsed_minutes >= 2:
            order.status = 'PREPARING'
            order.estimated_time = "30-40 Mins"
            order.save()
        elif order.status == 'PREPARING' and elapsed_minutes >= 25:
            order.status = 'OUT_FOR_DELIVERY'
            order.estimated_time = "10-20 Mins"
            order.save()
        elif order.status == 'OUT_FOR_DELIVERY' and elapsed_minutes >= 45:
            order.status = 'DELIVERED'
            order.estimated_time = "Ready / Bereit"
            order.save()
            
        if order.status != old_status:
            has_status_shifted = True

    unnotified_orders = OrderSummary.objects.filter(is_notified=False, status='PLACED')
    
    if unnotified_orders.exists() or has_status_shifted:
        unnotified_orders.update(is_notified=True)
        return JsonResponse({'new_order': True})
        
    return JsonResponse({'new_order': False})


def welcome_index(request):
    if request.user.is_authenticated:
        return redirect('home') 
    return render(request, 'booking/welcome.html')


# =====================================================================
# 8. DEDICATED OWNER NAVIGATION VIEW ENDPOINTS
# =====================================================================
@user_passes_test(lambda u: u.is_staff)
def owner_todays_orders(request):
    """
    Page 1: Today's Orders Pipeline Workspace.
    Tracks everything generated within the current local localized calendar cycle.
    """
    now = timezone.now()
    today_local = localtime(now).date()
    
    active_orders = OrderSummary.objects.filter(status__in=['PLACED', 'PREPARING', 'OUT_FOR_DELIVERY'])
    for order in active_orders:
        elapsed_minutes = (now - order.created_at).total_seconds() / 60.0
        if order.status == 'PLACED' and elapsed_minutes >= 2:
            order.status = 'PREPARING'
            order.estimated_time = "30-40 Mins"
            order.save()
        elif order.status == 'PREPARING' and elapsed_minutes >= 25:
            order.status = 'OUT_FOR_DELIVERY'
            order.estimated_time = "10-20 Mins"
            order.save()
        elif order.status == 'OUT_FOR_DELIVERY' and elapsed_minutes >= 45:
            order.status = 'DELIVERED'
            order.estimated_time = "Ready / Bereit"
            order.save()

    todays_orders = OrderSummary.objects.filter(
        created_at__date=today_local
    ).prefetch_related('items').order_by('-created_at')
    
    return render(request, 'booking/owner_todays_orders.html', {'orders': todays_orders})


@user_passes_test(lambda u: u.is_staff)
def owner_order_history(request):
    """
    Page 2: Comprehensive Closed History Log Archive.
    Groups ALL past transactions historically segregated by distinct local day dates.
    """
    today_local = localtime(timezone.now()).date()
    
    past_orders = OrderSummary.objects.filter(
        status__in=['DELIVERED', 'CANCELLED']
    ).exclude(created_at__date=today_local).prefetch_related('items').order_by('-created_at')
    
    segmented_history = {}
    for order in past_orders:
        local_date = localtime(order.created_at).date()
        if local_date not in segmented_history:
            segmented_history[local_date] = []
        segmented_history[local_date].append(order)
        
    return render(request, 'booking/owner_order_history.html', {
        'segmented_history': segmented_history
    })


@user_passes_test(lambda u: u.is_staff)
def owner_user_details(request):
    """Page 3: CRM Profile Ledger Ranked by Gross Investment Volume."""
    min_orders = request.GET.get('min_orders', '').strip()
    min_spend = request.GET.get('min_spend', '').strip()
    
    users_queryset = UserProfile.objects.all().select_related('user').annotate(
        total_spent=Sum('user__orders__final_amount'),
        order_count=Count('user__orders')
    )
    
    if min_orders.isdigit():
        users_queryset = users_queryset.filter(order_count__gte=int(min_orders))
        
    if min_spend:
        try:
            users_queryset = users_queryset.filter(total_spent__gte=Decimal(min_spend))
        except:
            pass
            
    users_queryset = users_queryset.order_by('-total_spent')
    
    for profile in users_queryset:
        if profile.total_spent is not None:
            profile.total_spent = Decimal(profile.total_spent).quantize(Decimal('0.01'))
        else:
            profile.total_spent = Decimal('0.00')
    
    return render(request, 'booking/owner_user_details.html', {
        'users': users_queryset,
        'min_orders': min_orders,
        'min_spend': min_spend
    })


@user_passes_test(lambda u: u.is_staff)
def delete_order_history(request, order_id):
    """Hard Row Purge Action forces system-wide currency metrics recalculations."""
    if request.method == 'POST':
        order = get_object_or_404(OrderSummary, id=order_id)
        order.delete()
    return redirect('owner_order_history')


@login_required
def cancel_order(request, order_id):
    """Allows customers to safely cancel an order if it is still in the 'PLACED' status."""
    order = get_object_or_404(OrderSummary, id=order_id, user=request.user)
    if order.status == 'PLACED':
        order.status = 'CANCELLED'
        order.canceled_by = 'CUSTOMER'  # Logs that the customer canceled it
        order.save()
    return redirect('dashboard')


@login_required
def reverse_geocode_address(request):
    """Converts coordinates to human-readable text via OpenStreetMap."""
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({'error': 'Missing coordinates.'}, status=400)
        
    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=jsonv2&lat={lat}&lon={lon}"
        headers = {'User-Agent': 'GaneshaRestaurantApp/1.0 (mdhanush)'}
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        if 'display_name' in data:
            return JsonResponse({'address': data['display_name']})
        return JsonResponse({'error': 'Address not found.'}, status=404)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)
    


@login_required
def update_cart_quantity(request, item_id):
    """Increments or decrements active cart items."""
    if request.method == 'POST':
        cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
        action = request.POST.get('action')
        
        if action == 'increase':
            cart_item.quantity += 1
            cart_item.save()
        elif action == 'decrease':
            cart_item.quantity -= 1
            if cart_item.quantity <= 0:
                cart_item.delete()
            else:
                cart_item.save()
                
    return redirect('view_cart')


@login_required
def reorder_past_items(request, order_id):
    """Re-adds dynamic historical line items back into the live cart."""
    old_order = get_object_or_404(OrderSummary, id=order_id, user=request.user)
    items_added_count = 0
    
    for historical_item in old_order.items.all():
        food_item = FoodItem.objects.filter(
            models.Q(name_de=historical_item.food_item_name) | 
            models.Q(name_en=historical_item.food_item_name),
            is_available=True
        ).first()
        
        if food_item:
            cart_item, created = CartItem.objects.get_or_create(
                user=request.user, 
                food_item=food_item,
                defaults={'quantity': historical_item.quantity}
            )
            if not created:
                cart_item.quantity += historical_item.quantity
                cart_item.save()
                
            items_added_count += 1

    if items_added_count > 0:
        return redirect('view_cart')
        
    return redirect('dashboard')


@login_required
def update_profile(request):
    """
    Handles real-time customer account profile updates (First Name, Last Name, 
    Email, Phone Number, and Default Delivery Address).
    Defensively gets or creates the UserProfile instance to prevent RelatedObjectDoesNotExist crashes.
    """
    user = request.user
    
    # 🚀 FIX: Safety hook dynamically builds the profile mapping layout if missing
    profile, created = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            'phone_number': user.username if user.username.startswith('+') else f"+4912345678",
            'address': "Admin Workspace Location"
        }
    )
    
    success_message = None
    error_message = None
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        country_code = request.POST.get('country_code', '+49').strip()
        phone_raw = request.POST.get('phone_raw', '').strip()
        address = request.POST.get('address', '').strip()
        
        # 🚀 Strips accidental leading zero input errors out dynamically
        if phone_raw.startswith('0'):
            phone_raw = phone_raw[1:]
            
        # Compile country prefix elements with the raw mobile digits cleanly
        phone = country_code + phone_raw
        
        if not first_name or not phone_raw:
            error_message = "Name and Phone number fields are required. / Name und Telefonnummer sind erforderlich."
        else:
            try:
                user.first_name = first_name
                user.last_name = last_name
                
                # Check if email is being changed and if it's already taken by someone else
                if email and User.objects.filter(email=email).exclude(id=user.id).exists():
                    error_message = "This email is already in use. / Diese E-Mail wird bereits verwendet."
                else:
                    user.email = email
                    user.save()
                    
                    # Update Custom Ganesha UserProfile fields together safely
                    profile.phone_number = phone
                    profile.address = address
                    profile.save()
                    
                    success_message = "Profile updated successfully! / Profil erfolgreich aktualisiert."
            except Exception as e:
                error_message = f"An error occurred during update: {e}"

    lang = request.session.get('lang', 'de')
    return render(request, 'booking/update_profile.html', {
        'success_message': success_message,
        'error_message': error_message,
        'lang': lang
    })