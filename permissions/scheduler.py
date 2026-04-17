from apscheduler.schedulers.background import BackgroundScheduler
from django.utils import timezone
from datetime import timedelta

def send_escalation_email(req, from_role, to_role, new_assignee):
    try:
        from django.core.mail import send_mail
        from django.conf import settings

        student_name = f"{req.student.first_name} {req.student.last_name}".strip() or req.student.username
        new_assignee_name = f"{new_assignee.first_name} {new_assignee.last_name}".strip() or new_assignee.username
        new_assignee_email = new_assignee.email

        # Email to new assignee
        if new_assignee_email:
            send_mail(
                subject=f"[{req.request_code}] Permission Request Escalated to You",
                message=f"""Hello {new_assignee_name},

A permission request has been auto-escalated to you as the previous authority ({from_role}) did not take action in time.

Request ID  : {req.request_code}
Title       : {req.title}
Requested By: {student_name}
Date Range  : {req.from_date} to {req.to_date}
Escalated From: {from_role.upper()}
Now Assigned To: {to_role.upper()}

Please login to CampusIQ and take action immediately.

Regards,
CampusIQ Team""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[new_assignee_email],
                fail_silently=True,
            )

        # Email to student
        student_email = req.student.email
        if student_email:
            send_mail(
                subject=f"[{req.request_code}] Your Request Has Been Auto-Escalated",
                message=f"""Hello {student_name},

Your permission request has been auto-escalated because the previous authority ({from_role}) did not respond in time.

Request ID    : {req.request_code}
Title         : {req.title}
Date Range    : {req.from_date} to {req.to_date}
Escalated From: {from_role.upper()}
Now Assigned To: {to_role.upper()}

Your request is still active and being reviewed.

Regards,
CampusIQ Team""",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[student_email],
                fail_silently=True,
            )

        print(f"[AutoEscalate] Emails sent for {req.request_code}")

    except Exception as e:
        print(f"[AutoEscalate EMAIL ERROR] {e}")


def send_reminder_email(req):
    try:
        from django.core.mail import send_mail
        from django.conf import settings

        if not req.request_to:
            return

        assignee_name  = f"{req.request_to.first_name} {req.request_to.last_name}".strip() or req.request_to.username
        assignee_email = req.request_to.email
        student_name   = f"{req.student.first_name} {req.student.last_name}".strip() or req.student.username

        if not assignee_email:
            return

        send_mail(
            subject=f"[URGENT REMINDER] [{req.request_code}] Action Required in 10 Minutes",
            message=f"""Hello {assignee_name},

This is an urgent reminder that the following permission request will be AUTO-ESCALATED in 10 minutes if no action is taken.

Request ID  : {req.request_code}
Title       : {req.title}
Requested By: {student_name}
Date Range  : {req.from_date} to {req.to_date}
Current Level: {req.current_level.upper()}

Please login to CampusIQ immediately and approve or reject this request.

Regards,
CampusIQ Team""",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[assignee_email],
            fail_silently=True,
        )

        print(f"[Reminder] 10-min reminder sent for {req.request_code} to {assignee_name}")

    except Exception as e:
        print(f"[Reminder EMAIL ERROR] {e}")


def auto_escalate_permissions():
    try:
        from permissions.models import PermissionRequest, RequestHistory
        from accounts.models import UserProfile
        from core.utils import create_notification

        ROLE_FLOW = {
            "student":  ["proctor", "staff", "hod", "dean", "principal"],
            "proctor":  ["hod", "dean", "principal"],
            "staff":    ["hod", "dean", "principal"],
            "hod":      ["dean", "principal"],
            "dean":     ["principal"],
            "principal": [],
        }

        now = timezone.now()

        # ── 10-minute reminder ─────────────────────────────
        reminder_window_start = now + timedelta(minutes=10)
        reminder_window_end   = now + timedelta(minutes=11)

        reminder_qs = PermissionRequest.objects.filter(
            status="pending",
            escalate_at__gte=reminder_window_start,
            escalate_at__lt=reminder_window_end,
            escalate_at__isnull=False,
        ).select_related("request_to", "student")

        for req in reminder_qs:
            send_reminder_email(req)

        # ── Auto escalation ────────────────────────────────
        overdue = PermissionRequest.objects.filter(
            status="pending",
            escalate_at__lte=now,
            escalate_at__isnull=False,
        ).select_related("request_to", "student")

        for req in overdue:
            if not req.request_to:
                continue

            current_profile = UserProfile.objects.filter(user=req.request_to).first()
            if not current_profile:
                continue

            current_role = (current_profile.role or "").strip().lower()
            allowed_next = ROLE_FLOW.get(current_role, [])

            if not allowed_next:
                req.status = "expired"
                req.escalate_at = None
                req.save(update_fields=["status", "escalate_at", "updated_at"])

                RequestHistory.objects.create(
                    request=req,
                    action="auto_escalated",
                    from_role=current_role,
                    to_role=None,
                    actor=None,
                    note="Reached top authority. No further escalation possible."
                )

                # Notify student it expired
                if req.student.email:
                    from django.core.mail import send_mail
                    from django.conf import settings
                    student_name = f"{req.student.first_name} {req.student.last_name}".strip() or req.student.username
                    send_mail(
                        subject=f"[{req.request_code}] Permission Request Expired",
                        message=f"""Hello {student_name},

Your permission request has reached the highest authority and could not be escalated further.

Request ID : {req.request_code}
Title      : {req.title}
Date Range : {req.from_date} to {req.to_date}
Status     : EXPIRED

Please contact your institution directly.

Regards,
CampusIQ Team""",
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[req.student.email],
                        fail_silently=True,
                    )
                continue

            dept = current_profile.department
            next_profile = None
            next_role = None

            for r in allowed_next:
                next_profile = UserProfile.objects.filter(
                    role=r,
                    department=dept
                ).select_related("user").first()
                if next_profile:
                    next_role = r
                    break

            if not next_profile:
                continue

            req.request_to    = next_profile.user
            req.current_level = next_role
            req.status        = "pending"
            req.escalate_at   = now + timedelta(hours=24)
            req.save(update_fields=[
                "request_to", "current_level",
                "status", "escalate_at", "updated_at"
            ])

            RequestHistory.objects.create(
                request=req,
                action="auto_escalated",
                from_role=current_role,
                to_role=next_role,
                actor=None,
                note=f"Auto-escalated from {current_role} to {next_role} due to no action"
            )

            create_notification(
                user=next_profile.user,
                title="Request Auto-Escalated to You",
                message=f"Request {req.request_code} was auto-escalated to you as previous authority took no action.",
                link="/accounts/dashboard/"
            )

            create_notification(
                user=req.student,
                title="Your Request Was Auto-Escalated",
                message=f"Your request {req.request_code} was auto-escalated to {next_role} as no action was taken.",
                link="/accounts/dashboard/"
            )

            # Send emails
            send_escalation_email(req, current_role, next_role, next_profile.user)

            print(f"[AutoEscalate] {req.request_code} escalated: {current_role} -> {next_role}")

    except Exception as e:
        print(f"[AutoEscalate ERROR] {e}")


def start():
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        auto_escalate_permissions,
        "interval",
        minutes=1,
        id="auto_escalate_permissions",
        replace_existing=True,
    )
    scheduler.start()
    print("[Scheduler] Auto-escalation scheduler started.")