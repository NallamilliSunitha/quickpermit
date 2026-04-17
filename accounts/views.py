# accounts/views.py  ✅ FULL UPDATED FILE (your same file, only updated request_permission + added email helper + imports)

from datetime import timedelta

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.db.models import Q
from meetings.models import Meeting
from .models import UserProfile, PasswordResetOTP
from permissions.models import PermissionRequest, RequestHistory
from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.conf import settings
from django.utils import timezone
from django.core.mail import send_mail
from meetings.models import Meeting

from django.db.models import Exists, OuterRef, Case, When, Value, IntegerField
from django.db.models import Max
from core.models import AcademicEvent
from django.contrib import messages
from datetime import datetime
from django.urls import reverse




from .models import PasswordResetOTP
import random



# -------------------- AUTH / REGISTER -------------------- #

from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib import messages
from .models import UserProfile

DEAN_TYPES = [
    "Academic Affairs",
    "R&D",
    "Student Affairs",
    "Placements",
]

def register(request):
    reg_type = (request.GET.get("type") or "student").strip().lower()

    # Allowed roles by entry point
    if reg_type == "student":
        allowed_roles = ["student"]
    elif reg_type == "employee":
        allowed_roles = ["staff", "hod", "dean"]
    elif reg_type == "principal":
        allowed_roles = ["principal"]
    else:
        allowed_roles = ["student"]

    if request.method == "POST":
        first_name = (request.POST.get("first_name") or "").strip()
        last_name  = (request.POST.get("last_name") or "").strip()
        username   = (request.POST.get("username") or "").strip()
        email      = (request.POST.get("email") or "").strip()
        password   = request.POST.get("password") or ""

        role = (request.POST.get("role") or "").strip().lower()

        # ✅ security: only allow valid roles for that register page
        if role not in allowed_roles:
            messages.error(request, "Invalid role selection for this registration page.")
            return redirect(f"{request.path}?type={reg_type}")

        # ✅ staff -> can become proctor (checkbox)
        is_proctor = (request.POST.get("is_proctor") == "on")
        if role == "staff" and is_proctor:
            role = "proctor"

        # ✅ collect department only when needed
        department = ""
        dean_type = ""

        if role in ("student", "staff", "proctor", "hod"):
            department = (request.POST.get("department") or "").strip()
            if not department:
                messages.error(request, "Department is required for this role.")
                return redirect(f"{request.path}?type={reg_type}")

        elif role == "dean":
            dean_type = (request.POST.get("dean_type") or "").strip()
            if dean_type not in DEAN_TYPES:
                messages.error(request, "Please select a valid Dean type.")
                return redirect(f"{request.path}?type={reg_type}")
            # no department for dean

        elif role == "principal":
            # no department for principal
            pass

        # ✅ unique username check
        if User.objects.filter(username=username).exists():
            messages.error(request, "Username / Roll number already exists!")
            return redirect(f"{request.path}?type={reg_type}")

        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=first_name,
            last_name=last_name,
            email=email,
        )

        # ✅ Save to profile
        # If your UserProfile doesn't have dean_type field yet, add it (instructions below)
        semester = request.POST.get("semester", "").strip() if role == "student" else ""
        profile = UserProfile.objects.create(
    user=user,
    role=role,
    department=department,
    semester=semester if role == "student" else None,
    is_approved=True
)
        if role == "dean":
            profile.dean_type = dean_type  # requires field in model
            profile.save(update_fields=["dean_type"])

        messages.success(request, "Account created successfully!")
        return redirect("login_home")

    return render(request, "accounts/register.html", {
        "allowed_roles": allowed_roles,
        "reg_type": reg_type,
        "dean_types": DEAN_TYPES,
    })



def login_home(request):
    return render(request, "accounts/login_home.html")




from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from .models import UserProfile

from django.contrib import messages

from django.contrib.auth import authenticate, login
from django.shortcuts import render, redirect
from django.contrib import messages
from .models import UserProfile


from django.contrib import messages

def _role_login(request, allowed_roles, template_name):

    # 🚨 BLOCK if already logged in
    if request.user.is_authenticated:
        messages.error(
            request,
            f"{request.user.username} is already logged in. Please logout first."
        )
        return redirect("dashboard")   # or "home"

    if request.method == "POST":
        username = (request.POST.get("username") or "").strip()
        password = request.POST.get("password") or ""

        user = authenticate(request, username=username, password=password)
        if not user:
            return render(request, template_name, {"error": "Invalid username or password", "next": request.POST.get("next", "")})

        profile = UserProfile.objects.filter(user=user).first()
        if not profile:
            return render(request, template_name, {"error": "Profile not found. Contact admin.", "next": request.POST.get("next", "")})

        role = (profile.role or "").strip().lower()
        if role not in [r.lower() for r in allowed_roles]:
            return render(request, template_name, {"error": "You are not allowed to login here.", "next": request.POST.get("next", "")})

        if not getattr(profile, "is_approved", False):
            return render(request, template_name, {"error": "Account not approved by admin", "next": request.POST.get("next", "")})

        login(request, user)

        next_url = request.POST.get("next") or request.GET.get("next")
        if next_url:
            return redirect(next_url)

        return redirect("dashboard")

    return render(request, template_name, {"next": request.GET.get("next", "")})
def student_login(request):
    return _role_login(request, ["student"], "accounts/student_login.html")


def principal_login(request):
    return _role_login(request, ["principal"], "accounts/principal_login.html")


def employee_login(request):
    return _role_login(request, ["staff", "proctor", "hod", "dean"], "accounts/employee_login.html")


# -------------------- DASHBOARD -------------------- #

@login_required
def dashboard(request):
    user = request.user
    profile = UserProfile.objects.filter(user=user).first()
    role = (profile.role or "").strip().lower() if profile else ""

    roll_number = user.first_name or user.username
    if role == "student" and profile and getattr(profile, "roll_number", None):
        roll_number = profile.roll_number

    submitted_requests = (
        PermissionRequest.objects
        .filter(student=user)
        .select_related("request_to")
        .order_by("-applied_at")
    )

    received_requests = (
        PermissionRequest.objects
        .filter(request_to=user)
        .select_related("student", "ai_insight")
        .annotate(
            is_urgent_rank=Case(
                When(is_urgent=True, status="pending", then=Value(0)),
                When(status="pending", then=Value(1)),
                When(status="approved", then=Value(2)),
                When(status="rejected", then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            ),
            was_auto_escalated=Exists(
                RequestHistory.objects.filter(
                    request_id=OuterRef("pk"),
                    action="auto_escalated"
                )
            ),
        )
        .order_by("is_urgent_rank", "-was_auto_escalated", "-applied_at")
    )

    submitted_counts = {
        "total": submitted_requests.count(),
        "pending": submitted_requests.filter(status="pending").count(),
        "approved": submitted_requests.filter(status="approved").count(),
        "rejected": submitted_requests.filter(status="rejected").count(),
    }

    received_counts = {"pending": 0, "approved": 0, "rejected": 0}
    if role != "student":
        received_counts["approved"] = received_requests.filter(status="approved").count()
        received_counts["rejected"] = received_requests.filter(status="rejected").count()
        received_counts["pending"] = received_requests.filter(status="pending", current_level=role).count()

    # ✅ invited meetings for logged-in user
    my_meetings = (
    Meeting.objects
    .filter(Q(recipients__user=user) | Q(created_by=user))
    .select_related("created_by")
    .distinct()
    .order_by("scheduled_at", "-created_at")
)
    today = timezone.now().date()

    today_meetings = my_meetings.filter(scheduled_at__date=today).order_by("scheduled_at")
    upcoming_meetings = my_meetings.filter(scheduled_at__date__gt=today).order_by("scheduled_at")
    cancelled_meetings = my_meetings.filter(status="cancelled").order_by("-scheduled_at")
    context = {
        "profile": profile,
        "roll_number": roll_number,
        "submitted_requests": submitted_requests,
        "received_requests": received_requests,
        "total": submitted_counts["total"],
        "pending": submitted_counts["pending"],
        "approved": submitted_counts["approved"],
        "rejected": submitted_counts["rejected"],
        "received_counts": received_counts,
        "now": timezone.now(),
        "my_meetings": my_meetings,
        "today_meetings": today_meetings,
        "upcoming_meetings": upcoming_meetings,
        "cancelled_meetings": cancelled_meetings,   # ✅ pass to template
    }
    return render(request, "dashboard/dashboard.html", context)

# -------------------- EMAIL HELPER (NEW) -------------------- #

def _full_name_or_username(u):
    full = (f"{u.first_name} {u.last_name}").strip()
    return full if full else (u.username or "User")


def _send_assigned_email(req):
    """
    Sends email to:
    1. Assigned authority — new request assigned to them
    2. Student — confirmation that request was submitted
    """
    from django.core.mail import send_mail
    from django.conf import settings

    request_id     = req.request_code or f"REQ-{req.id:06d}"
    title          = (req.title or "Permission Request").strip()
    student_name   = _full_name_or_username(req.student)
    authority_name = _full_name_or_username(req.request_to) if req.request_to else "Authority"

    # ── Email to authority ──────────────────────────
    try:
        if req.request_to and req.request_to.email:
            to_email = req.request_to.email.strip()
            send_mail(
                subject=f"[{request_id}] New Permission Request Assigned to You",
                message=(
                    f"Hello {authority_name},\n\n"
                    f"A new permission request has been assigned to you for review.\n\n"
                    f"Request ID : {request_id}\n"
                    f"Student    : {student_name} ({req.student.username})\n"
                    f"Title      : {title}\n"
                    f"From Date  : {req.from_date}\n"
                    f"To Date    : {req.to_date}\n"
                    f"Urgent     : {'YES — Action required within time limit' if req.is_urgent else 'NO'}\n"
                    f"Status     : {req.status.upper()}\n\n"
                    f"Please login to CampusIQ and review it from your dashboard.\n"
                    f"https://sunitha11.pythonanywhere.com/dashboard/\n\n"
                    f"Regards,\nCampusIQ Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[to_email],
                fail_silently=False,
            )
            print(f"[SUBMITTED] Authority email sent to {to_email}")
        else:
            print(f"[SUBMITTED] No authority email for {request_id} — skipping authority email")
    except Exception as e:
        print(f"[SUBMITTED] Authority email failed: {e}")

    # ── Confirmation email to student ───────────────
    try:
        student_email = (req.student.email or "").strip()
        if student_email:
            send_mail(
                subject=f"[{request_id}] Permission Request Submitted Successfully",
                message=(
                    f"Hello {student_name},\n\n"
                    f"Your permission request has been submitted successfully "
                    f"and assigned for review.\n\n"
                    f"Request ID  : {request_id}\n"
                    f"Title       : {title}\n"
                    f"From Date   : {req.from_date}\n"
                    f"To Date     : {req.to_date}\n"
                    f"Assigned To : {authority_name}\n"
                    f"Urgent      : {'YES' if req.is_urgent else 'NO'}\n\n"
                    f"You can track your request from your dashboard.\n"
                    f"https://sunitha11.pythonanywhere.com/dashboard/\n\n"
                    f"Regards,\nCampusIQ Team"
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[student_email],
                fail_silently=False,
            )
            print(f"[SUBMITTED] Student confirmation sent to {student_email}")
        else:
            print(f"[SUBMITTED] No student email for {request_id} — skipping student email")
    except Exception as e:
        print(f"[SUBMITTED] Student email failed: {e}")


# -------------------- REQUEST PERMISSION (UPDATED) -------------------- #

from datetime import timedelta
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.conf import settings
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import Max

from accounts.models import UserProfile
from permissions.models import PermissionRequest, RequestHistory
from core.models import AcademicEvent
from core.utils import create_notification


@login_required
def request_permission(request):
    profile = request.user.userprofile
    my_role = (profile.role or "").strip().lower()

    if my_role == "student":
        roles = ["proctor", "staff", "hod", "dean", "principal"]
    elif my_role in ("staff", "proctor"):
        roles = ["hod", "dean", "principal"]
    elif my_role == "hod":
        roles = ["dean", "principal"]
    elif my_role == "dean":
        roles = ["principal"]
    else:
        roles = []

    users_by_role = {}
    for role in roles:
        if role in ["dean", "principal"]:
            qs = UserProfile.objects.filter(role=role)
        else:
            qs = UserProfile.objects.filter(role=role, department=profile.department)
        users_by_role[role] = list(
        qs.select_related("user")
        .values("user__id", "user__first_name", "user__last_name", "user__username")
    )

    if request.method == "POST":
        selected_user_id = request.POST.get("request_to")
        from_date = request.POST.get("from_date")
        to_date = request.POST.get("to_date")

        if not selected_user_id:
            messages.error(request, "Please select an authority.")
            return redirect("request_permission")

        if not from_date or not to_date:
            messages.error(request, "Please select From Date and To Date.")
            return redirect("request_permission")

        blocked = AcademicEvent.objects.filter(
            is_blocked=True,
            department=profile.department,
            event_date__range=[from_date, to_date]
        ).exists()

        if blocked:
            messages.error(
                request,
                "Selected dates conflict with an important academic event/exam. Please choose different dates."
            )
            return redirect("request_permission")

        selected_user = User.objects.filter(id=selected_user_id).first()
        if not selected_user:
            return HttpResponseForbidden("Selected user not found")

        target_profile = UserProfile.objects.filter(user=selected_user).first()
        if not target_profile:
            return HttpResponseForbidden("Selected user has no profile")

        target_role = (target_profile.role or "").strip().lower()

        max_id = PermissionRequest.objects.aggregate(Max("id"))["id__max"] or 0
        request_code = f"REQ-{max_id + 1:06d}"

        is_urgent = request.POST.get("is_urgent") == "on"
        urgent_minutes = request.POST.get("urgent_minutes")

        if is_urgent:
            try:
                m = int(urgent_minutes or 0)
            except:
                m = getattr(settings, "URGENT_MIN_MINUTES", 10)
            m = max(getattr(settings, "URGENT_MIN_MINUTES", 10),
                    min(getattr(settings, "URGENT_MAX_MINUTES", 360), m))
            escalate_at = timezone.now() + timedelta(minutes=m)
        else:
            escalate_at = timezone.now() + timedelta(
                hours=getattr(settings, "NORMAL_ESCALATION_HOURS", 24)
            )

        req = PermissionRequest.objects.create(
            student=request.user,
            request_to=selected_user,
            request_code=request_code,
            title=request.POST.get("title") or "",
            reason=request.POST.get("reason") or "",
            from_date=from_date,
            to_date=to_date,
            current_level=target_role,
            file=request.FILES.get("permission_file"),
            is_urgent=is_urgent,
            escalate_at=escalate_at,
            urgent_minutes=m if is_urgent else None
        )

        RequestHistory.objects.create(
            request=req,
            action="created",
            from_role=my_role,
            to_role=target_role,
            actor=request.user,
            note="Request created"
        )

        create_notification(
            user=request.user,
            title="Request Submitted",
            message=f"Your request ({req.request_code}) was submitted successfully.",
            link=reverse("request_detail", args=[req.id])
            )

        create_notification(
            user=selected_user,
            title="New Permission Request",
            message=f"{request.user.username} submitted request ({req.request_code}).",
            link=reverse("request_detail", args=[req.id])
)
        try:
            _send_assigned_email(req)
        except Exception:
            pass

        messages.success(request, "Permission request submitted successfully!")
        return redirect("dashboard")

    # Fix: use timezone.now().date() instead of timezone.localdate()
    today = timezone.now().date()

    return render(request, "permissions/permission.html", {
        "users_by_role": users_by_role,
        "profile": profile,
        "today": today,
    })
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

@login_required
def my_requests(request):
    user = request.user
    requests_qs = (
        PermissionRequest.objects
        .filter(student=user)
        .select_related("request_to")
        .order_by("-applied_at")
    )
    return render(
        request,
        "dashboard/my_requests.html",
        {
            "requests": requests_qs,
            "now": timezone.now(),
        },
    )

# -------------------- FILE TEXT EXTRACT -------------------- #

from PyPDF2 import PdfReader
import docx

def extract_text_from_file(uploaded_file):
    """
    Returns extracted text from pdf/doc/docx.
    If extraction fails, returns empty string.
    """
    if not uploaded_file:
        return ""

    name = uploaded_file.name.lower()

    try:
        if name.endswith(".pdf"):
            reader = PdfReader(uploaded_file)
            text = []
            for page in reader.pages:
                text.append(page.extract_text() or "")
            return "\n".join(text).strip()

        if name.endswith(".docx"):
            d = docx.Document(uploaded_file)
            return "\n".join([p.text for p in d.paragraphs]).strip()

        if name.endswith(".doc"):
            return ""

    except Exception:
        return ""

    return ""
def forgot_password(request):
    if request.method == "POST":
        username = request.POST.get("username")

        user = User.objects.filter(username=username).first()

        if not user:
            return render(request, "accounts/forgot_password.html", {
                "error": "User not registered."
            })

        otp = str(random.randint(100000, 999999))

        # delete old OTPs
        PasswordResetOTP.objects.filter(user=user).delete()

        PasswordResetOTP.objects.create(
            user=user,
            otp=otp
        )

        send_mail(
            subject="CampusIQ Password Reset OTP",
            message=f"Your OTP is: {otp}\n\nValid for 5 minutes.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False
        )

        request.session["reset_user"] = user.id

        return redirect("verify_otp")

    return render(request, "accounts/forgot_password.html")
def verify_otp(request):
    user_id = request.session.get("reset_user")

    if not user_id:
        return redirect("forgot_password")

    user = User.objects.get(id=user_id)

    if request.method == "POST":
        entered_otp = request.POST.get("otp")

        otp_obj = PasswordResetOTP.objects.filter(user=user).first()

        if not otp_obj:
            return render(request, "accounts/verify_otp.html", {
                "error": "OTP not found."
            })

        if otp_obj.is_expired():
            otp_obj.delete()
            return render(request, "accounts/verify_otp.html", {
                "error": "OTP expired."
            })

        if otp_obj.otp != entered_otp:
            return render(request, "accounts/verify_otp.html", {
                "error": "Invalid OTP."
            })

        return redirect("reset_password")

    return render(request, "accounts/verify_otp.html")
def reset_password(request):
    user_id = request.session.get("reset_user")

    if not user_id:
        return redirect("forgot_password")

    user = User.objects.get(id=user_id)

    if request.method == "POST":
        password = request.POST.get("password")
        confirm = request.POST.get("confirm_password")

        if password != confirm:
            return render(request, "accounts/reset_password.html", {"error": "Passwords do not match."
    })

        user.set_password(password)
        user.save()

        PasswordResetOTP.objects.filter(user=user).delete()
        del request.session["reset_user"]

        return redirect("login_home")

    return render(request, "accounts/reset_password.html")
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from accounts.models import UserProfile
from permissions.models import PermissionRequest, RequestHistory

ROLES = ["student", "proctor", "staff", "hod", "dean", "principal"]

@login_required
def analytics_dashboard(request):
    now = timezone.now()

    # ---------
    # ROLE USERS
    # ---------
    role_users = (
        UserProfile.objects
        .filter(role__in=ROLES)
        .select_related("user")
    )

    # Map role -> [user_ids]
    role_to_user_ids = {r: [] for r in ROLES}
    for p in role_users:
        role_to_user_ids[(p.role or "").strip().lower()].append(p.user_id)

    # -------------------------
    # ROLE-LEVEL "RECEIVED" DATA
    # -------------------------
    role_summary = []
    for role in ROLES:
        uids = role_to_user_ids.get(role, [])

        received_total = PermissionRequest.objects.filter(request_to_id__in=uids).count()
        received_pending = PermissionRequest.objects.filter(request_to_id__in=uids, status__iexact="pending").count()

        # Actions done by people in that role (from history actor)
        approved = RequestHistory.objects.filter(action__iexact="approved", actor_id__in=uids).count()
        rejected = RequestHistory.objects.filter(action__iexact="rejected", actor_id__in=uids).count()
        forwarded = RequestHistory.objects.filter(action__iexact="forwarded", actor_id__in=uids).count()
        reassigned = RequestHistory.objects.filter(action__iexact="reassigned", actor_id__in=uids).count()
        auto_escalated = RequestHistory.objects.filter(action__iexact="auto_escalated", from_role__iexact=role).count()

        # Student "taken" means submitted
        submitted = PermissionRequest.objects.filter(student__in=uids).count() if role == "student" else None

        role_summary.append({
            "role": role,
            "submitted": submitted,  # only for student
            "received_total": received_total,
            "received_pending": received_pending,
            "approved": approved,
            "rejected": rejected,
            "forwarded": forwarded,
            "reassigned": reassigned,
            "auto_escalated": auto_escalated,
        })

    # --------------------------------------
    # USER-LEVEL TABLE (counts per user/role)
    # --------------------------------------
    # Received by user
    received_by_user = (
        PermissionRequest.objects
        .values("request_to_id")
        .annotate(total=Count("id"), pending=Count("id", filter=Q(status__iexact="pending")))
    )
    received_map = {x["request_to_id"]: x for x in received_by_user}

    # Action counts by user (history.actor)
    actions = ["approved", "rejected", "forwarded", "reassigned"]
    action_maps = {}
    for a in actions:
        rows = (
            RequestHistory.objects
            .filter(action__iexact=a, actor__isnull=False)
            .values("actor_id")
            .annotate(c=Count("id"))
        )
        action_maps[a] = {r["actor_id"]: r["c"] for r in rows}

    # Auto escalated by from_role (not actor)
    # but to show per-user "auto escalated", you can count history where note contains old assignee,
    # or better: store old_request_to in history later. If you can't, keep per-role only.
    # We'll keep per-role only to stay within your "don't change logic" rule.

    users_table = []
    for p in role_users:
        uid = p.user_id
        role = (p.role or "").strip().lower()

        rec = received_map.get(uid, {"total": 0, "pending": 0})
        users_table.append({
            "role": role,
            "user_id": uid,
            "name": (p.user.get_full_name() or p.user.username),
            "username": p.user.username,
            "received_total": rec.get("total", 0),
            "received_pending": rec.get("pending", 0),
            "approved": action_maps["approved"].get(uid, 0),
            "rejected": action_maps["rejected"].get(uid, 0),
            "forwarded": action_maps["forwarded"].get(uid, 0),
            "reassigned": action_maps["reassigned"].get(uid, 0),
        })

    # Sort by role then received_total desc
    users_table.sort(key=lambda x: (ROLES.index(x["role"]) if x["role"] in ROLES else 999, -x["received_total"]))

    return render(request, "analytics/role_analytics.html", {
        "now": now,
        "role_summary": role_summary,
        "users_table": users_table,
        "roles": ROLES,
    })
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Q, Case, When, Value, IntegerField, Exists, OuterRef

from accounts.models import UserProfile
from permissions.models import PermissionRequest, RequestHistory
from certificates.models import CertificateRequest
from meetings.models import Meeting


from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from core.models import Notification
from accounts.models import UserProfile   # adjust if path differs

@login_required
def module_hub(request):
    user = request.user
    profile = UserProfile.objects.filter(user=user).first()

    # ✅ Get unread notifications count
    unread_count = Notification.objects.filter(
        user=user,
        is_read=False
    ).count()

    context = {
        "profile": profile,
        "unread_count": unread_count   # ✅ ADD THIS
    }

    return render(request, "dashboard/module_hub.html", context)


@login_required
def permission_module(request):
    user = request.user
    profile = UserProfile.objects.filter(user=user).first()
    role = (profile.role or "").strip().lower() if profile else ""

    roll_number = user.first_name or user.username
    if role == "student" and profile and getattr(profile, "roll_number", None):
        roll_number = profile.roll_number

    submitted_requests = (
        PermissionRequest.objects
        .filter(student=user)
        .select_related("request_to")
        .order_by("-applied_at")
    )

    received_requests = (
        PermissionRequest.objects
        .filter(request_to=user)
        .select_related("student", "ai_insight")
        .annotate(
            is_urgent_rank=Case(
                When(is_urgent=True, status="pending", then=Value(0)),
                When(status="pending", then=Value(1)),
                When(status="approved", then=Value(2)),
                When(status="rejected", then=Value(3)),
                default=Value(9),
                output_field=IntegerField(),
            ),
            was_auto_escalated=Exists(
                RequestHistory.objects.filter(
                    request_id=OuterRef("pk"),
                    action="auto_escalated"
                )
            ),
        )
        .order_by("is_urgent_rank", "-was_auto_escalated", "-applied_at")
    )

    submitted_counts = {
        "total": submitted_requests.count(),
        "pending": submitted_requests.filter(status="pending").count(),
        "approved": submitted_requests.filter(status="approved").count(),
        "rejected": submitted_requests.filter(status="rejected").count(),
    }

    received_counts = {"pending": 0, "approved": 0, "rejected": 0}
    if role != "student":
        received_counts["approved"] = received_requests.filter(status="approved").count()
        received_counts["rejected"] = received_requests.filter(status="rejected").count()
        received_counts["pending"] = received_requests.filter(status="pending", current_level=role).count()

    context = {
        "profile": profile,
        "roll_number": roll_number,
        "submitted_requests": submitted_requests,
        "received_requests": received_requests,
        "total": submitted_counts["total"],
        "pending": submitted_counts["pending"],
        "approved": submitted_counts["approved"],
        "rejected": submitted_counts["rejected"],
        "received_counts": received_counts,
        "now": timezone.now(),
    }
    return render(request, "dashboard/permission_module.html", context)

@login_required
def certificate_module(request):
    user = request.user
    profile = UserProfile.objects.filter(user=user).first()
    role = (profile.role or "").strip().lower() if profile else ""

    my_certificate_requests = (
        CertificateRequest.objects
        .filter(student=user)
        .select_related("request_to")
        .order_by("-created_at")
    )

    received_certificate_requests = CertificateRequest.objects.none()
    if role in ["staff", "proctor", "hod", "dean", "principal"]:
        received_certificate_requests = (
            CertificateRequest.objects
            .filter(request_to=user)
            .select_related("student")
            .order_by("-created_at")
        )

    approved_count = my_certificate_requests.filter(status="approved").count()
    pending_count = my_certificate_requests.filter(status="pending").count()
    rejected_count = my_certificate_requests.filter(status="rejected").count()

    context = {
        "profile": profile,
        "my_certificate_requests": my_certificate_requests,
        "received_certificate_requests": received_certificate_requests,
        "approved_count": approved_count,
        "pending_count": pending_count,
        "rejected_count": rejected_count,
    }
    return render(request, "dashboard/certificate_module.html", context)

@login_required
def meeting_module(request):
    user = request.user
    profile = UserProfile.objects.filter(user=user).first()

    # Use UTC date for comparison since DB stores UTC
    from django.utils import timezone
    import datetime
    today_utc = datetime.date(2026, 3, 12)  # hardcoded won't work
    # Correct way:
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)

    all_meetings = Meeting.objects.filter(
        Q(created_by=user) | Q(recipients__user=user)
    ).select_related("created_by").distinct()

    my_meetings = all_meetings.order_by("-scheduled_at")

    # Fix: use range instead of __date
    today_meetings = all_meetings.filter(
    scheduled_at__range=(today_start, today_end)
).exclude(status="cancelled")

    upcoming_meetings = all_meetings.filter(
        scheduled_at__gt=today_end,
        status="scheduled"
    )

    cancelled_meetings = all_meetings.filter(
        status="cancelled"
    )

    context = {
        "profile":            profile,
        "my_meetings":        my_meetings,
        "today_meetings":     today_meetings,
        "upcoming_meetings":  upcoming_meetings,
        "cancelled_meetings": cancelled_meetings,
        "now":                timezone.now(),
    }
    return render(request, "dashboard/meeting_module.html", context)
from django.http import JsonResponse
from core.models import Notification

def unread_notifications_api(request):
    if not request.user.is_authenticated:
        return JsonResponse({"count": 0, "notifications": []})

    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]

    data = []
    for n in notifications:
        data.append({
            "id": n.id,   # ✅ IMPORTANT
            "title": n.title,
            "message": n.message,
            "link": n.link   # ✅ IMPORTANT
        })

    return JsonResponse({
        "count": notifications.count(),
        "notifications": data
        })
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import os
from django.conf import settings

@login_required
def profile_page(request):
    profile = request.user.userprofile

    if request.method == "POST":
        # Update user fields
        request.user.first_name = request.POST.get("first_name", request.user.first_name)
        request.user.last_name  = request.POST.get("last_name", request.user.last_name)
        request.user.email      = request.POST.get("email", request.user.email)

        # Update profile fields
        profile.department = request.POST.get("department", profile.department)
        profile.semester   = request.POST.get("semester", profile.semester)
        profile.college    = request.POST.get("college", profile.college)

        # Handle photo upload
        new_photo = request.FILES.get("photo")
        if new_photo:
            # Delete old photo if exists
            if profile.photo and os.path.isfile(profile.photo.path):
                os.remove(profile.photo.path)

            profile.photo = new_photo  # Save new photo

        # Save everything
        request.user.save()
        profile.save()

        messages.success(request, "Profile updated successfully!")
        return redirect("profile_page")

    return render(request, "accounts/profile.html", {"profile": profile})
from django.contrib.auth.views import LogoutView
from accounts.models import UserProfile

class CustomLogoutView(LogoutView):

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            profile = UserProfile.objects.filter(user=request.user).first()
            if profile:
                profile.is_logged_in = False
                profile.save()

        return super().dispatch(request, *args, **kwargs)