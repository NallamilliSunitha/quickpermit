from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from permissions.models import PermissionRequest, RequestHistory
from accounts.models import UserProfile

# ── ROLE FLOW ─────────────────────────────────────────────
ROLE_ORDER = ["staff", "proctor", "hod", "dean", "principal"]


def get_next_role(current_level):
    current_level = (current_level or "").strip().lower()

    if current_level in ["staff", "proctor"]:
        return "hod"
    elif current_level == "hod":
        return "dean"
    elif current_level == "dean":
        return "principal"
    else:
        return None


def get_next_user(req):
    student_profile = getattr(req.student, "userprofile", None)
    dept = getattr(student_profile, "department", None)

    current = req.current_level

    while True:
        next_role = get_next_role(current)
        if not next_role:
            return None, None

        qs = UserProfile.objects.filter(role=next_role)

        if next_role not in ["dean", "principal"] and dept:
            qs = qs.filter(department=dept)

        profile = qs.select_related("user").first()

        if profile:
            return next_role, profile.user

        # skip role if not found
        current = next_role


def _full_name(user):
    full = (f"{user.first_name} {user.last_name}").strip()
    return full if full else user.username


# ══════════════════════════════════════════════════════════════
# AUTO ESCALATION
# ══════════════════════════════════════════════════════════════

def auto_escalate_permissions():
    now = timezone.now()

    expired_requests = PermissionRequest.objects.filter(
        status="pending",
        escalate_at__isnull=False,
        escalate_at__lte=now
    ).select_related("student", "request_to")

    count = 0

    for req in expired_requests:
        old_user = req.request_to
        old_role = req.current_level

        next_role, next_user = get_next_user(req)

        if not next_role:
            print(f"[ESCALATION] {req.request_code}: Already at top level")
            continue

        if not next_user:
            print(f"[ESCALATION] {req.request_code}: No {next_role} found")
            continue

        # ── UPDATE REQUEST ─────────────────────────────
        req.current_level = next_role
        req.request_to = next_user

        # ✅ FIXED ESCALATION LOGIC
        if req.is_urgent and req.urgent_minutes:
            level_multiplier = {
                "proctor": 1,
                "staff": 1,
                "hod": 2,
                "dean": 3,
                "principal": 4,
            }

            base = req.urgent_minutes
            multiplier = level_multiplier.get(next_role, 1)
            minutes = base * multiplier
        else:
            hours = getattr(settings, "NORMAL_ESCALATION_HOURS", 24)
            minutes = hours * 60

        req.escalate_at = now + timezone.timedelta(minutes=minutes)

        # ✅ reset reminder tracking
        req.warning_sent_at = None

        req.save(update_fields=[
            "current_level",
            "request_to",
            "escalate_at",
            "warning_sent_at"
        ])

        # ── HISTORY ────────────────────────────────────
        RequestHistory.objects.create(
            request=req,
            action="auto_escalated",
            from_role=old_user.userprofile.role if old_user else old_role,
            to_role=next_role,
            actor=None,
            note=f"Auto-escalated from {old_role} to {next_role}"
        )

        # ── NOTIFICATIONS ──────────────────────────────
        try:
            from core.utils import create_notification

            create_notification(
                user=next_user,
                title=f"Escalated Request: {req.title}",
                message=f"{req.request_code} escalated to you from {old_role.upper()}",
                link=f"/permissions/view/{req.id}/"
            )

            create_notification(
                user=req.student,
                title=f"Request Escalated: {req.request_code}",
                message=f"Your request moved to {next_role.upper()}",
                link=f"/permissions/track/{req.id}/"
            )
        except Exception as e:
            print(f"[ESCALATION NOTIFICATION ERROR] {e}")

        # ── EMAIL TO AUTHORITY ─────────────────────────
        if next_user.email:
            try:
                send_mail(
                    subject=f"[CampusIQ] Escalated: {req.request_code}",
                    message=f"Request {req.request_code} needs your action.",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[next_user.email],
                    fail_silently=False,
                )
            except Exception as e:
                print(f"[ESCALATION EMAIL ERROR] {e}")

        print(f"[ESCALATION] {req.request_code}: {old_role} → {next_role}")
        count += 1

    print(f"[ESCALATION DONE] {count}")
    return count


# ══════════════════════════════════════════════════════════════
# URGENT REMINDERS
# ══════════════════════════════════════════════════════════════

def send_urgent_reminders():
    """
    Sends reminder emails every 5 minutes
    in the last 15 minutes before escalation
    """

    now = timezone.now()

    interval_minutes = 5   # send every 5 min
    window_minutes = 15    # last 15 min

    upcoming = PermissionRequest.objects.filter(
        status="pending",
        is_urgent=True,
        escalate_at__isnull=False,
        escalate_at__gt=now
    ).select_related("student", "request_to")

    count = 0

    for req in upcoming:
        minutes_left = (req.escalate_at - now).total_seconds() / 60

        print(f"[DEBUG] {req.request_code} → {minutes_left:.2f} mins left")

        # ✅ only last 15 minutes
        if not (0 <= minutes_left <= window_minutes):
            continue

        if not req.request_to or not req.request_to.email:
            continue

        # ⛔ prevent spam
        last_sent = req.warning_sent_at
        if last_sent:
            diff = (now - last_sent).total_seconds() / 60
            if diff < interval_minutes:
                continue

        try:
            send_mail(
                subject=f"⚠️ URGENT Reminder: {req.request_code}",
                message=f"""
Request {req.request_code} will escalate soon!

Time left: {round(minutes_left, 1)} minutes

Student: {_full_name(req.student)}
Title: {req.title}

Please take action immediately.
""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[req.request_to.email],
                fail_silently=False,
            )

            req.warning_sent_at = now
            req.save(update_fields=["warning_sent_at"])

            RequestHistory.objects.create(
                request=req,
                action="urgent_warning_sent",
                from_role=req.current_level,
                to_role=req.current_level,
                actor=None,
                note="Urgent reminder sent"
            )

            print(f"[REMINDER SENT] {req.request_code}")
            count += 1

        except Exception as e:
            print(f"[REMINDER ERROR] {req.request_code}: {e}")

    print(f"[REMINDERS DONE] {count}")
    return count