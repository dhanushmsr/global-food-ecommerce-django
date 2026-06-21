from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import OrderSummary

@receiver(post_save, sender=OrderSummary)
def auto_email_on_status_change(sender, instance, created, **kwargs):
    """
    Listens directly to the database model fields. Fires an instant email 
    the moment an order status is edited locally or on the live dashboard.
    """
    # 🎯 DELAYED IMPORT: Injected inside the block to completely eliminate startup circular loops!
    from .views import trigger_status_milestone_email  
    
    # Execute the milestone parsing engine wrapper
    trigger_status_milestone_email(order_summary=instance)