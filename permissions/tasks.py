from celery import shared_task
from django.utils import timezone
from django.contrib.auth.models import User
from permissions.models import PermissionRequest, RequestHistory
from accounts.models import UserProfile
from django.core.mail import send_mail
from django.conf import settings


def get_next_role(current_level: str):
    order = ["staff", "proctor", "hod", "dean", "principal"]
    current_level = (current_level or "").strip().lower()
    if current_level not in order:
        return None
    idx = order.index(current_level)
    if idx + 1 >= len(order):
        return None
    return order[idx + 1]


def get_next_user_for_request(req):
    next_role = get_next_role(req.current_level)
    if not next_role:
        return None, None

    qs = UserProfile.objects.filter(role=next_role)

    student_profile = getattr(req.student, "userprofile", None)
    student_dept = getattr(student_profile, "department", None)

    if next_role not in ["dean", "principal"] and student_dept:
        qs = qs.filter(department=student_dept)

    profile = qs.select_related("user").first()
    if not profile:
        return next_role, None

    return next_role, profile.user


@shared_task
def run_auto_escalation():
    now = timezone.now()

    expired = PermissionRequest.objects.filter(
        status="pending",
        is_urgent=True,
        escalate_at__isnull=False,
        escalate_at__lte=now,
    ).select_related("student", "request_to")

    for req in expired:
        next_role, next_user = get_next_user_for_request(req)

        if not next_role or not next_user:
            continue

        old_user = req.request_to

        req.current_level = next_role
        req.request_to = next_user
        req.escalate_at = now + timezone.timedelta(minutes=10)
        req.save(update_fields=["current_level", "request_to", "escalate_at"])

        RequestHistory.objects.create(
            request=req,
            action="auto_escalated",
            from_user=old_user,
            to_user=next_user,
            comments="Automatically escalated due to timeout."
        )

        if next_user.email:
            try:
                send_mail(
                    f"Auto Escalated Request: {req.title}",
                    f"""
A permission request has been auto-escalated to you.

Title: {req.title}
Student: {req.student.username}
Current Level: {req.current_level.upper()}

Reason:
Automatically escalated due to timeout.

Regards,
CampusIQ
""",
                    settings.DEFAULT_FROM_EMAIL,
                    [next_user.email],
                    fail_silently=True,
                )
            except Exception:
                pass