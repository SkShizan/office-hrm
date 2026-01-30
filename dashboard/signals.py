from django.db.models.signals import post_save
from django.dispatch import receiver
from accounts.models import User
from .models import LeaveBalance
from django.core.mail import send_mail
from django.conf import settings

@receiver(post_save, sender=User)
def create_user_setup(sender, instance, created, **kwargs):
    if created:
        # 1. Auto-Create Leave Balance
        LeaveBalance.objects.create(user=instance)
        
        # 2. Send Welcome Email
        subject = 'Welcome to the HRMS System'
        message = f'Hi {instance.username}, your account has been created. Please wait for HR approval.'
        if instance.role == 'HR':
             message = f'Hi {instance.username}, your Company {instance.company.name} is registered.'
        
        # Fail silently ensures the app doesn't crash if email server is down
        send_mail(subject, message, settings.EMAIL_HOST_USER, [instance.email], fail_silently=True)