from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse, HttpResponseBadRequest
from django.conf import settings
from django.core.mail import send_mail, EmailMessage  # Native fallback utilities
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages 
from django.utils import timezone
from django.utils.timezone import localtime  # 🚀 CRITICAL TIMEZONE LOCALIZATION HOOK
from django.db import models                   # Injects models namespace for Q objects
from django.db.models import Sum, Count
from .models import FoodCategory, FoodItem, Coupon, CartItem, OrderSummary, OrderBreakdownItem, UserProfile, PromoAnnouncement
from decimal import Decimal
from django.template.loader import render_to_string  
from django.views.decorators.csrf import csrf_exempt
from mollie.api.client import Client             # 🚀 INJECTED: Mollie Payment SDK Engine Client Hook
import requests                                  # Required for live lookups and Brevo REST API transmissions
import threading                                 
import random
import re

# =====================================================================
# 🚀 TIME ENGINE: 55-MINUTE AUTO-PILOT
# =====================================================================
def auto_update_order_timeline(order):
    """
    Calculates elapsed time and shifts order status automatically.
    """
    if order.status in ['DELIVERED', 'CANCELLED', 'failed', 'completed']:
        return order

    now = timezone.now()
    elapsed = now - order.created_at
    elapsed_mins = int(elapsed.total_seconds() / 60)

    needs_save = False

    # PHASE 1: 0 to 5 Mins -> PLACED (Received)
    if elapsed_mins < 5:
        if order.status in ['verifying', 'ordered']:
            order.status = 'PLACED'
            needs_save = True
        if order.estimated_time != "55 Min":
            order.estimated_time = "55 Min"
            needs_save = True

    # PHASE 2: 5 to 25 Mins -> PREPARING (Kitchen)
    elif 5 <= elapsed_mins < 25:
        if order.status != 'PREPARING':
            order.status = 'PREPARING'
            needs_save = True
        new_eta = f"{55 - elapsed_mins} Min"
        if order.estimated_time != new_eta:
            order.estimated_time = new_eta
            needs_save = True

    # PHASE 3: 25 to 55 Mins -> OUT_FOR_DELIVERY (Transit)
    elif 25 <= elapsed_mins < 55:
        if order.status != 'OUT_FOR_DELIVERY':
            order.status = 'OUT_FOR_DELIVERY'
            needs_save = True
        new_eta = f"{55 - elapsed_mins} Min"
        if order.estimated_time != new_eta:
            order.estimated_time = new_eta
            needs_save = True

    # PHASE 4: 55+ Mins -> DELIVERED (Complete)
    elif elapsed_mins >= 55:
        if order.status != 'DELIVERED':
            order.status = 'DELIVERED'
            order.estimated_time = 'Geliefert'
            needs_save = True

    if needs_save:
        order.save(update_fields=['status', 'estimated_time'])

    return order

# =====================================================================
# LIVE NETWORK DISPATCH UTILITY INFRASTRUCTURE (BREVO HTTPS API ENGINE)
# =====================================================================
import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException

def send_live_api_email(first_name, email, email_otp):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['eyJhcGlfa2V5IjoieGtleXNpYi0zNDcwOTE4MzZkZmJkNWFlOGQxMGExM2VjMmE5YTZlMGI5NTEyMmUyNmFjNjYyYWUyOTgyNTQwMmM3YjJmYTk0LTcyRmxTOWJjOXVzUEtiZEoifQ=='] = 'YOUR_BREVO_API_KEY_HERE'
    
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))
    
    html_content = f"""
    <html>
    <body style='font-family: Arial, sans-serif; padding: 20px; color: #333;'>
        <h2 style='color: #dc3545;'>Namaste {first_name},</h2>
        <p>Thank you for your request at Ganesha! Please use the validation key below:</p>
        <div style='background-color: #f8f9fa; padding: 15px; border-radius: 8px; border: 1px solid #dee2e6; display: inline-block; margin: 15px 0;'>
            <span style='font-size: 24px; font-weight: bold; letter-spacing: 2px; color: #dc3545;'>{email_otp}</span>
        </div>
        <p style='font-size: 12px; color: #6c757d;'>Valid for 10 minutes.</p>
    </body>
    </html>
    """
    
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": email, "name": first_name}],
        html_content=html_content,
        sender={"name": "Ganesha Portal", "email": "info@ganeshamuehlacker.com"},
        subject="Ganesha Portal - Identity Verification Action Required"
    )
    
    try:
        api_instance.send_transac_email(send_smtp_email)
        print(f"📧 [BREVO API SUCCESS] OTP sent to {email}")
        return True
    except ApiException as e:
        print(f"❌ [BREVO API FAILURE]: {e}")
        return False

def send_live_api_sms(phone_number, email_otp, message_type="verification"):
    subject = f"Ganesha System Alert - SMS Fallback Log ({message_type.upper()})"
    
    if message_type == "reset":
        msg_content = f"Password reset recovery token generated for user tracking line {phone_number}: Key = {email_otp}."
    else:
        msg_content = f"Identity verification token generated for user tracking line {phone_number}: Key = {email_otp}."
        
    try:
        send_mail(
            subject=subject,
            message=msg_content,
            from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@ganeshamuehlacker.com'),
            recipient_list=[getattr(settings, 'EMAIL_HOST_USER', 'info@ganeshamuehlacker.com')],
            fail_silently=False,
        )
        print(f"📱 [SMS FALLBACK SUCCESS] Token log safely queued for cellular tracking on {phone_number}")
        return True
    except Exception as log_err:
        print(f"❌ Local cPanel system notification drop: {log_err}")
        return False


from django.db import connections 

def trigger_status_milestone_email(order_summary):
    if not order_summary.user.email:
        return False
        
    def send_async_milestone():
        try:
            connections.close_all()
            
            html_content = render_to_string('booking/email_receipt.html', {'order': order_summary})
            email_msg = EmailMessage(
                subject=f"Ganesha Restaurant - Status-Update / Order Info #{order_summary.id}",
                body=html_content,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@ganeshamuehlacker.com'),
                to=[order_summary.user.email]
            )
            email_msg.content_subtype = "html"
            email_msg.send(fail_silently=False)
            print(f"📬 [MILESTONE SUCCESS] Automated update email sent to {order_summary.user.email}")
        except Exception as e:
            print(f"⚠️ Milestone email delivery worker encounter block: {e}")

    threading.Thread(target=send_async_milestone).start()
    return True

# =====================================================================
# 1. MULTILINGUAL & PUBLIC WELCOME DISPLAY
# =====================================================================
def set_language(request):
    lang = request.GET.get('lang', 'de')
    request.session['lang'] = lang
    return redirect(request.META.get('HTTP_REFERER', 'home'))


def welcome_index(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    promos = PromoAnnouncement.objects.all()
    coupons = Coupon.objects.filter(specific_user__isnull=True, active=True).select_related('applicable_category')
    
    universal_offers = []
    for coupon in coupons:
        display_image = None
        
        if coupon.applicable_category:
            featured_item = FoodItem.objects.filter(category=coupon.applicable_category, is_available=True).exclude(image='').first()
            if featured_item:
                display_image = featured_item.image.url
                
        if not display_image:
            fallback_item = FoodItem.objects.filter(is_available=True).exclude(image='').first()
            if fallback_item:
                display_image = fallback_item.image.url

        universal_offers.append({
            'coupon': coupon,
            'display_image': display_image,
        })
        
    context = {
        'universal_offers': universal_offers,
        'promos': promos,
    }
        
    return render(request, 'booking/welcome.html', context)


# =====================================================================
# 2. GUEST AUTHENTICATION (NO OTP)
# =====================================================================
def register_user(request):
    error = None
    if request.method == 'POST':
        country_code = request.POST.get('country_code', '+49').strip()
        phone_raw = request.POST.get('phone_raw', '').strip()
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password')
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        address = request.POST.get('address', '').strip()
        
        if phone_raw.startswith('0'):
            phone_raw = phone_raw[1:]
            
        phone = country_code + phone_raw
        
        if len(password) < 8:
            error = "Password must be at least 8 characters long. / Mindestens 8 Zeichen erforderlich."
        elif not re.search(r'[A-Z]', password):
            error = "Password must contain at least one uppercase letter. / Mindestens ein Großbuchstabe erforderlich."
        elif not re.search(r'[!@#$%^&*(),.?":{}|<>_+-]', password):
            error = "Password must contain at least one special character. / Mindestens ein Sonderzeichen erforderlich."
        elif User.objects.filter(username=phone).exists():
            error = "This phone number is already registered. / Diese Nummer ist bereits registriert."
        elif User.objects.filter(email=email).exists():
            error = "This email is already registered. / Diese E-Mail ist bereits registriert."
        else:
            try:
                user = User.objects.create_user(
                    username=phone, 
                    email=email,
                    password=password,
                    first_name=first_name, 
                    last_name=last_name
                )
                
                UserProfile.objects.create(
                    user=user, 
                    phone_number=phone, 
                    address=address,
                    email_verified=True,  
                    phone_verified=True   
                )
                
                login(request, user)
                messages.success(request, "Account created successfully! Welcome to Ganesha.")
                return redirect('home')
                
            except Exception as e:
                print(f"DEBUG: Creation error: {e}")
                error = "An error occurred during registration. / Ein Fehler ist aufgetreten."
            
    return render(request, 'booking/register.html', {'error': error})


def login_user(request):
    error = None
    if request.method == 'POST':
        phone = request.POST.get('phone', '').strip()
        
        if phone and not phone.startswith('+'):
            if phone.isalpha():
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
            
            email_subject = "Ganesha Restaurant - Reset Security Access Token"
            email_body = f"Namaste {profile.user.first_name},\n\nWe received a request to update your secure access password credentials. Use the security key below to complete the validation check:\n\nReset Verification Code: {profile.password_reset_otp}\n\nThis token is valid for 10 minutes."
            
            try:
                send_mail(
                    subject=email_subject,
                    message=email_body,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@ganesha.com'),
                    recipient_list=[profile.user.email],
                    fail_silently=False,
                )
                
                send_live_api_sms(phone, profile.password_reset_otp, message_type="reset")
                request.session['reset_password_phone'] = phone
                return redirect('forgot_password_verify')
            except Exception as e:
                error = f"Mail system drop encountered: {str(e)}"
                print(f"❌ Password recovery dispatch drop: {e}")
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
        elif len(new_password) < 8:
            error = "Password must be at least 8 characters long. / Mindestens 8 Zeichen erforderlich."
        elif not re.search(r'[A-Z]', new_password):
            error = "Password must contain at least one uppercase letter. / Mindestens ein Großbuchstabe erforderlich."
        elif not re.search(r'[!@#$%^&*(),.?":{}|<>_+-]', new_password):
            error = "Password must contain at least one special character. / Mindestens ein Sonderzeichen erforderlich."
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
    lang = request.session.get('lang', 'de')
    categories = FoodCategory.objects.all()
    menu_items = FoodItem.objects.filter(is_available=True)
    available_coupons = Coupon.objects.filter(specific_user__isnull=True, active=True).exclude(used_by=request.user)
    
    cart_quantities = {}
    if request.user.is_authenticated:
        cart_items = CartItem.objects.filter(user=request.user)
        for item in cart_items:
            cart_quantities[item.food_item_id] = item.quantity

    return render(request, 'booking/home.html', {
        'categories': categories, 
        'menu_items': menu_items,
        'lang': lang,
        'cart_quantities': cart_quantities,
        'universal_offers': available_coupons
    })


# =====================================================================
# 4. FRONTEND CONTENT & INVENTORY MANAGEMENT (STAFF / OWNER CONTROL)
# =====================================================================
@user_passes_test(lambda u: u.is_staff)
def add_modify_menu(request, item_id=None):
    if request.method == 'POST' and request.POST.get('action_type') == 'UPLOAD_PROMO':
        promo_image = request.FILES.get('promo_image')
        promo_video = request.FILES.get('promo_video')
        notes_en = request.POST.get('notes_en', '').strip()
        notes_de = request.POST.get('notes_de', '').strip()

        PromoAnnouncement.objects.create(
            image=promo_image,
            video=promo_video,
            notes_en=notes_en,
            notes_de=notes_de
        )
        return redirect('hotel_management')

    if request.method == 'POST' and request.POST.get('action_type') == 'DELETE_PROMO':
        promo_id = request.POST.get('promo_id')
        try:
            promo_item = PromoAnnouncement.objects.get(id=promo_id)
            if promo_item.image:
                promo_item.image.delete(save=False)
            if promo_item.video:
                promo_item.video.delete(save=False)
            promo_item.delete()
        except PromoAnnouncement.DoesNotExist:
            pass
        return redirect('hotel_management')

    item = FoodItem.objects.filter(id=item_id).first() if item_id else None
    
    if request.method == 'POST':
        action = request.POST.get('action_type', 'UPDATE')
        
        if action == 'DELETE' and item:
            item.delete()
            return redirect('hotel_management')
            
        category_id = request.POST.get('category')
        if not category_id:
            default_cat, _ = FoodCategory.objects.get_or_create(name_de="Allgemein", name_en="General")
            category_id = default_cat.id
            
        if not item:
            item = FoodItem()
            
        item.category_id = category_id
        item.name_en = request.POST.get('name_en')
        item.name_de = request.POST.get('name_de')
        item.description_en = request.POST.get('description_en', '')
        item.description_de = request.POST.get('description_de', '')
        item.price = request.POST.get('price')
        item.diet_type = request.POST.get('diet_type')
        item.item_type = request.POST.get('item_type', 'FOOD') 
        
        image_file = request.FILES.get('image')
        if image_file:
            item.image = image_file
            
        item.save()
            
    return redirect('hotel_management')


@user_passes_test(lambda u: u.is_staff)
def add_category_frontend(request, cat_id=None):
    if request.method == 'POST':
        cat_id = request.POST.get('category_id') or cat_id
        action = request.POST.get('action_type', 'CREATE')
        
        if cat_id:
            category = get_object_or_404(FoodCategory, id=cat_id)
            if action == 'DELETE':
                category.delete()
                return redirect('hotel_management')
                
            category.name_en = request.POST.get('name_en', '').strip()
            category.name_de = request.POST.get('name_de', '').strip()
            category.save()
        else:
            name_en = request.POST.get('name_en', '').strip()
            name_de = request.POST.get('name_de', '').strip()
            if name_en and name_de:
                FoodCategory.objects.get_or_create(name_en=name_en, defaults={'name_de': name_de})
                
    return redirect('hotel_management')


@user_passes_test(lambda u: u.is_staff)
def add_coupon_frontend(request):
    if request.method == 'POST':
        coupon_id = request.POST.get('coupon_id')
        action = request.POST.get('action_type', 'DELETE')
        
        if coupon_id and action == 'DELETE':
            coupon = get_object_or_404(Coupon, id=coupon_id)
            coupon.delete()
            return redirect('hotel_management')
            
        code = request.POST.get('code', '').strip().upper()
        discount = int(request.POST.get('discount_percentage', 0))
        min_order = Decimal(request.POST.get('min_order_amount', '0.00'))
        user_id = request.POST.get('specific_user_id')
        cat_id = request.POST.get('applicable_category_id')
        
        specific_user = User.objects.filter(id=user_id).first() if user_id else None
        applicable_category = FoodCategory.objects.filter(id=cat_id).first() if cat_id else None
        
        if code:
            if coupon_id:
                coupon = get_object_or_404(Coupon, id=coupon_id)
                coupon.code = code
                coupon.discount_percentage = discount
                coupon.min_order_amount = min_order
                coupon.specific_user = specific_user
                coupon.applicable_category = applicable_category
                coupon.save()
            else:
                Coupon.objects.update_or_create(
                    code=code,
                    defaults={
                        'discount_percentage': discount,
                        'specific_user': specific_user,
                        'min_order_amount': min_order,
                        'applicable_category': applicable_category,
                        'active': True
                    }
                )
                
    return redirect('hotel_management')


# =====================================================================
# 5. CART ECOSYSTEM & TARGETED CATEGORY VAT CHECKOUT ENGINE
# =====================================================================
@login_required
def add_to_cart(request, item_id):
    food_item = get_object_or_404(FoodItem, id=item_id)
    cart_item, created = CartItem.objects.get_or_create(user=request.user, food_item=food_item)
    
    if not created:
        cart_item.quantity += 1
        cart_item.save()
        
    if request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.GET.get('ajax') == 'true':
        total_items = CartItem.objects.filter(user=request.user).aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        
        return JsonResponse({
            'success': True,
            'message': f"{food_item.name_en} added!",
            'cart_total': total_items
        })
        
    return redirect(request.META.get('HTTP_REFERER', 'home'))

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
                
                if coupon_match.applicable_category:
                    applicable_items_total = sum(
                        item.food_item.price * item.quantity 
                        for item in cart_items 
                        if item.food_item.category == coupon_match.applicable_category
                    )
                    discount = (applicable_items_total * Decimal(coupon_match.discount_percentage)) / Decimal(100)
                else:
                    discount = (subtotal * Decimal(coupon_match.discount_percentage)) / Decimal(100)
        else:
            coupon_error = "Invalid or expired voucher code. / Ungültiger Gutschein."

    discount_ratio = Decimal('1.00')
    if subtotal > 0:
        discount_ratio = (subtotal - discount) / subtotal

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
    universal_offers = Coupon.objects.filter(specific_user__isnull=True, active=True)

    if request.method == 'POST':
        if not cart_items.exists():
            return redirect('home')
            
        chosen_type = request.POST.get('order_type', 'DELIVERY')
        fallback_address = request.POST.get('address', 'Selected Option: ' + chosen_type)
        raw_payment_method = request.POST.get('payment_method', 'COD')
        
        if chosen_type == 'DELIVERY' and final_amount < Decimal('25.00'):
            messages.error(request, "Minimum order amount for delivery is 25.00€. / Mindestbestellwert für Lieferung ist 25,00€.")
            return redirect('view_cart')
        
        if raw_payment_method == 'online':
            db_payment_method = 'MOLLIE'
        else:
            db_payment_method = raw_payment_method  
        
        if coupon_obj and coupon_obj.used_by.filter(id=request.user.id).exists():
            return redirect('view_cart')
            
        order = OrderSummary.objects.create(
            user=request.user, 
            delivery_address=fallback_address if chosen_type == 'DELIVERY' else "Fulfillment Mode: " + chosen_type,
            phone_number=request.POST.get('phone'), 
            payment_method=db_payment_method,      
            order_type=chosen_type,
            subtotal=subtotal, 
            gst_amount=combined_tax.quantize(Decimal('0.01')),
            final_amount=final_amount.quantize(Decimal('0.01')),
            coupon_applied=coupon_obj,
            status='verifying',
            estimated_time='55 Min' 
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
        
        if raw_payment_method == 'online':
            return redirect('payment_checkout', order_id=order.id)
            
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
        'exclusive_offers': exclusive_offers,
        'universal_offers': universal_offers 
    })


@login_required
def update_cart_quantity(request, item_id):
    cart_item = get_object_or_404(CartItem, food_item_id=item_id, user=request.user)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'increase':
            cart_item.quantity += 1
            cart_item.save()
        elif action == 'decrease':
            cart_item.quantity -= 1
            cart_item.save()
            if cart_item.quantity <= 0:
                cart_item.delete()
                
    return redirect('view_cart')


# =====================================================================
# 6. MOLLIE SECURE TRANSACTION PIPELINE CONTROLLERS
# =====================================================================
@login_required
def initiate_mollie_payment(request, order_id):
    order = get_object_or_404(OrderSummary, id=order_id, user=request.user)
    
    order.payment_status = 'Pending'
    order.payment_method = 'MOLLIE'
    order.status = 'verifying' 
    order.save()
    
    mollie_client = Client()
    mollie_client.set_api_key("live_GBATHyzFj3mkShQJgSqNr7GcptESVc")
    
    try:
        dynamic_price = f"{order.final_amount:.2f}" 
        
        payment_payload = {
            'amount': {
                'currency': 'EUR',
                'value': dynamic_price  
            },
            'description': f'Ganesha Restaurant - Order #{order.id}',
            'redirectUrl': f'https://ganeshamuehlacker.com/payment/success/{order.id}/',
            'cancelUrl': f'https://ganeshamuehlacker.com/payment/cancel/{order.id}/',
            'metadata': {
                'order_id': str(order.id)  
            }
        }
        
        payment = mollie_client.payments.create(payment_payload)
        request.session['mollie_payment_id'] = payment.id
        
        print(f"🚀 [MOLLIE REDIRECT] Sending user to checkout URL: {payment.checkout_url}")
        return redirect(payment.checkout_url)
        
    except Exception as payment_err:
        print("\n" + "="*50)
        print(f"❌ MOLLIE GATEWAY API ERROR LOG:\n{payment_err}")
        print("="*50 + "\n")
        messages.error(request, f"Port 443 Handshake Intercept: {payment_err}")
        return redirect('dashboard')


@login_required
def payment_success_view(request, order_id):
    order = get_object_or_404(OrderSummary, id=order_id, user=request.user)
    mollie_payment_id = request.session.get('mollie_payment_id')

    if mollie_payment_id:
        try:
            mollie_client = Client()
            mollie_client.set_api_key("live_GBATHyzFj3mkShQJgSqNr7GcptESVc")  
            payment = mollie_client.payments.get(mollie_payment_id)
            
            if payment.is_paid():
                order.payment_status = 'Paid'
                order.status = 'ordered' 
                order.save()
                
                CartItem.objects.filter(user=request.user).delete()
                messages.success(request, "Payment captured successfully!")
            elif payment.is_open() or payment.is_pending():
                order.payment_status = 'Pending'
                order.save()
            else:
                order.payment_status = 'Failed'
                order.status = 'failed'
                order.save()
                
        except Exception as verify_err:
            print(f"❌ Mollie Security Verification Handshake Dropped: {verify_err}")
            order.payment_status = 'Pending'
            order.save()
    else:
        order.payment_status = 'Pending'
        order.save()

    context = {
        'order': order,
        'lang': request.session.get('lang', 'de'),
    }
    return render(request, 'booking/bill_invoice.html', context)


@login_required
def payment_cancel_view(request, order_id):
    order = get_object_or_404(OrderSummary, id=order_id, user=request.user)
    
    order.payment_status = 'Cancelled'
    order.status = 'cancelled' 
    order.save()
    
    context = {
        'order': order,
        'lang': request.session.get('lang', 'de')
    }
    return render(request, 'booking/bill_invoice.html', context)


@csrf_exempt
def mollie_webhook_view(request):
    if request.method == 'POST':
        payment_id = request.POST.get('id')
        if not payment_id:
            return HttpResponseBadRequest("Missing dynamic payload token reference handle metadata.")
            
        mollie_client = Client()
        mollie_client.set_api_key("live_GBATHyzFj3mkShQJgSqNr7GcptESVc")  
        
        try:
            payment = mollie_client.payments.get(payment_id)
            order_id = payment.metadata.get('order_id')
            
            if payment.is_paid():
                order = OrderSummary.objects.filter(id=order_id).first()
                if order:
                    order.payment_status = 'Paid'
                    if order.status != 'cancelled' and order.status != 'failed':
                        order.status = 'ordered'
                    order.save()
                    print(f"✅ [WEBHOOK PAID SUCCESS] Order Summary database model #{order_id} committed as PAID.")
                    
            return HttpResponse("OK")
        except Exception as webhook_err:
            print(f"❌ Webhook background runtime exception encountered: {webhook_err}")
            return HttpResponse("Internal Failure Engine Webhook Handler", status=500)
            
    return HttpResponseBadRequest("Invalid request interface layout method.")


# =====================================================================
# 7. DIGITAL INVOICES & REVENUE TRACKING LOGS
# =====================================================================
@login_required
def view_bill(request, order_id):
    order = get_object_or_404(OrderSummary, id=order_id)
    if not request.user.is_staff and order.user != request.user:
        return redirect('home')
        
    auto_update_order_timeline(order)
        
    if order.payment_method == 'MOLLIE' and order.payment_status == 'Pending':
        time_elapsed = timezone.now() - order.created_at
        if time_elapsed.total_seconds() > 300: 
            old_status = order.status
            order.payment_status = 'Failed'
            order.status = 'failed' 
            order.canceled_by = 'OWNER'  
            order.save()
            
            if order.status != old_status:
                trigger_status_milestone_email(order)

    return render(request, 'booking/bill_invoice.html', {'order': order})


@login_required
def dashboard(request):
    stale_orders = OrderSummary.objects.filter(
        user=request.user,
        payment_method='MOLLIE',
        payment_status='Pending',
        created_at__lt=timezone.now() - timezone.timedelta(minutes=5)
    )
    
    if stale_orders.exists():
        stale_orders.update(
            payment_status='Failed',
            status='cancelled', 
            canceled_by='OWNER'
        )

    orders = OrderSummary.objects.filter(user=request.user).order_by('-created_at')
    
    for order in orders:
        auto_update_order_timeline(order)
        
    return render(request, 'booking/dashboard.html', {'orders': orders})


# =====================================================================
# 8. BUSINESS DASHBOARD & ADMINISTRATIVE PORTS (OWNER CONFIGURATION)
# =====================================================================
@user_passes_test(lambda u: u.is_staff)
def hotel_owner_dashboard(request):
    now = timezone.now()
    
    active_orders = OrderSummary.objects.exclude(status__in=['DELIVERED', 'CANCELLED', 'failed', 'completed'])
    for order in active_orders:
        auto_update_order_timeline(order)

    all_orders = OrderSummary.objects.all().order_by('-created_at')
    active_queue_orders = all_orders.exclude(status__in=['completed', 'cancelled', 'failed']).prefetch_related('items')
    
    all_users = UserProfile.objects.all().select_related('user')
    all_menu_items = FoodItem.objects.all().select_related('category')
    all_categories = FoodCategory.objects.all() 
    all_coupons = Coupon.objects.all() 
    all_promos = PromoAnnouncement.objects.all() 
    
    today_local = localtime(now).date()
    todays_orders = all_orders.filter(created_at__date=today_local)
    
    raw_todays_revenue = todays_orders.exclude(status__in=['cancelled', 'failed']).aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0.00')
    todays_revenue = Decimal(raw_todays_revenue).quantize(Decimal('0.01'))
    todays_orders_count = todays_orders.filter(status__in=['ordered', 'preparing', 'delivered', 'completed']).count()
    
    raw_grand_revenue = all_orders.exclude(status__in=['cancelled', 'failed']).aggregate(Sum('final_amount'))['final_amount__sum'] or Decimal('0.00')
    grand_total_revenue = Decimal(raw_grand_revenue).quantize(Decimal('0.01'))

    return render(request, 'booking/hotel_management.html', {
        'orders': active_queue_orders,
        'users': all_users,
        'menu_items': all_menu_items,
        'categories': all_categories, 
        'all_coupons': all_coupons,
        'todays_revenue': todays_revenue,
        'todays_count': todays_orders_count,
        'grand_total_revenue': grand_total_revenue,
        'promos': all_promos,
    })


@user_passes_test(lambda u: u.is_staff)
def update_order_logistics(request, order_id):
    if request.method == 'POST':
        order = get_object_or_404(OrderSummary, id=order_id)
        new_status = request.POST.get('status', 'preparing')
        
        order.estimated_time = request.POST.get('estimated_time', '40-45 Mins')
        order.status = new_status
        
        if new_status == 'cancelled':
            order.canceled_by = 'OWNER'
            
        order.save()
    return redirect(request.META.get('HTTP_REFERER', 'hotel_management'))


def check_new_orders_api(request):
    now = timezone.now()
    has_status_shifted = False
    
    active_orders = OrderSummary.objects.exclude(status__in=['DELIVERED', 'CANCELLED', 'failed', 'completed'])
    for order in active_orders:
        old_status = order.status
        auto_update_order_timeline(order)
        if order.status != old_status:
            has_status_shifted = True

    stale_checkouts = OrderSummary.objects.filter(
        payment_method='MOLLIE',
        payment_status='Pending',
        created_at__lt=now - timezone.timedelta(minutes=5)
    )
    if stale_checkouts.exists():
        stale_checkouts.update(payment_status='Failed', status='cancelled', canceled_by='OWNER')
        has_status_shifted = True

    fresh_incoming_window = now - timezone.timedelta(seconds=12)
    new_incoming_orders_exist = OrderSummary.objects.filter(
        status__in=['verifying', 'PLACED', 'ordered'],
        created_at__gte=fresh_incoming_window
    ).exists()

    if new_incoming_orders_exist:
        has_status_shifted = True

    return JsonResponse({'new_order': has_status_shifted, 'refresh_needed': has_status_shifted})

# =====================================================================
# 9. DEDICATED OWNER NAVIGATION VIEW ENDPOINTS
# =====================================================================
@user_passes_test(lambda u: u.is_staff)
def owner_todays_orders(request):
    now = timezone.now()
    today_local = localtime(now).date()
    
    active_orders = OrderSummary.objects.exclude(status__in=['DELIVERED', 'CANCELLED', 'failed', 'completed'])
    for order in active_orders:
        auto_update_order_timeline(order)

    todays_orders = OrderSummary.objects.filter(
        created_at__date=today_local
    ).prefetch_related('items').order_by('-created_at')
    
    return render(request, 'booking/owner_todays_orders.html', {'orders': todays_orders})


@user_passes_test(lambda u: u.is_staff)
def owner_order_history(request):
    today_local = localtime(timezone.now()).date()
    
    past_orders = OrderSummary.objects.filter(
        status__in=['completed', 'cancelled', 'failed']
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
    if request.method == 'POST':
        order = get_object_or_404(OrderSummary, id=order_id)
        order.delete()
    return redirect('owner_order_history')


@login_required
def cancel_order(request, order_id):
    order = get_object_or_404(OrderSummary, id=order_id, user=request.user)
    
    allowed_states = ['ordered', 'PLACED', 'PREPARING', 'verifying']
    if order.status not in allowed_states:
        return redirect('dashboard')

    if request.method == 'POST':
        dropdown_reason = request.POST.get('reason_select', '').strip()
        custom_text_reason = request.POST.get('reason_text', '').strip()
        
        if custom_text_reason:
            reason_summary = f"{dropdown_reason} | Additional Info: {custom_text_reason}"
        else:
            reason_summary = dropdown_reason
        
        order.status = 'CANCELLED'
        order.canceled_by = 'CUSTOMER'
        
        if hasattr(order, 'cancellation_notes') or hasattr(order, 'reason'):
            if hasattr(order, 'cancellation_notes'):
                order.cancellation_notes = reason_summary
            else:
                order.reason = reason_summary
                
        order.save()
        return redirect('dashboard')
        
    lang = request.session.get('lang', 'de')
    return render(request, 'booking/cancel_order_form.html', {
        'order': order,
        'lang': lang
    })


@login_required
def reorder_past_items(request, order_id):
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
def reverse_geocode_address(request):
    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    
    if not lat or not lon:
        return JsonResponse({'error': 'Missing coordinates.'}, status=404)
        
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


# =====================================================================
# 10. SECURITY BOUND PROFILE LIFECYCLE CONTROLLERS (NO OTP UPDATE)
# =====================================================================
@login_required
def update_profile(request):
    user = request.user
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    success_message = None
    error_message = None
    
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        country_code = request.POST.get('country_code', '+49').strip()
        phone_raw = request.POST.get('phone_raw', '').strip()
        address = request.POST.get('address', '').strip()
        
        if phone_raw.startswith('0'):
            phone_raw = phone_raw[1:]
        phone = country_code + phone_raw
        
        if not first_name or not phone_raw:
            error_message = "Name and Phone number are required."
        else:
            try:
                # Check for duplicate Email (Exclude current user)
                if email and User.objects.filter(email=email).exclude(id=user.id).exists():
                    error_message = "This email is already in use."
                
                # Check for duplicate Phone (Exclude current profile)
                elif UserProfile.objects.filter(phone_number=phone).exclude(user=user).exists():
                    error_message = "This phone number is already registered by another user."
                
                else:
                    # 🎯 DIRECT UPDATE - NO OTP REQUIRED
                    is_phone_changed = (phone != profile.phone_number)

                    user.first_name = first_name
                    user.last_name = last_name
                    user.email = email
                    
                    if is_phone_changed:
                        user.username = phone  # Sync login credential with new phone number
                        
                    user.save()
                    
                    profile.phone_number = phone
                    profile.address = address
                    profile.save()
                    
                    if is_phone_changed:
                        logout(request)
                        messages.success(request, "Phone number updated successfully! Please log in again with your new number.")
                        return redirect('login')
                    else:
                        success_message = "Profile updated successfully!"

            except Exception as e:
                error_message = f"An error occurred: {e}"

    lang = request.session.get('lang', 'de')
    return render(request, 'booking/update_profile.html', {
        'success_message': success_message,
        'error_message': error_message,
        'lang': lang,
        'profile': profile
    })


def terms_conditions(request):
    return render(request, 'booking/terms.html', {
        'lang': request.session.get('lang', 'de')
    })

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.views.decorators.http import require_POST

@login_required
@require_POST  # Only allow POST requests for security
def delete_profile(request):
    user = request.user
    # Deleting the user object will cascade delete the related UserProfile
    # and all associated orders if your models are set up correctly.
    user.delete()
    logout(request)
    return redirect('welcome')