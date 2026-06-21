# C:\Users\mdhan\Desktop\skrt\core\booking\context_processors.py
from django.db.models import Sum
from .models import CartItem

def cart_counter_processor(request):
    """
    Globally injects the aggregate total item count of the user's shopping cart.
    """
    if request.user.is_authenticated:
        total = CartItem.objects.filter(user=request.user).aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        return {'cart_total_count': total}
    return {'cart_total_count': 0}


def language_context(request):
    """
    🚀 FIX: Globally injects the active session language ('de' or 'en') 
    so it is available on every template without manual view assignment.
    """
    return {
        'lang': request.session.get('lang', 'de')
    }