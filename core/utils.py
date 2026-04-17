from django.conf import settings
from django.core.mail import send_mail
from .models import Notification
from core.models import Notification

def create_notification(user, title, message, link=""):
    if not user:
        return
    Notification.objects.create(
        user=user,
        title=title,
        message=message,
        link=link or ""
    )


def push_notification(user, title, message="", link=""):
    if not user:
        return
    Notification.objects.create(user=user, title=title, message=message, link=link)

def send_email_if_possible(to_email, subject, body):
    if not to_email:
        return
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [to_email], fail_silently=False)
# accounts/models.py
