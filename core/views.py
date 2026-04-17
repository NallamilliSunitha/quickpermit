from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from .models import Notification
from django.http import HttpResponseForbidden
from django.db.models import Count, Q

from accounts.models import UserProfile
from permissions.models import PermissionRequest, RequestHistory

@login_required
def notifications_page(request):
    qs = Notification.objects.filter(user=request.user)
    return render(request, "core/notifications.html", {"items": qs})

@login_required
def notifications_api(request):
    qs = Notification.objects.filter(user=request.user).values("id", "title", "message", "link", "is_read", "created_at")[:50]
    return JsonResponse({"ok": True, "items": list(qs)})

@login_required
def mark_read(request, pk):
    n = get_object_or_404(Notification, pk=pk, user=request.user)
    n.is_read = True
    n.save(update_fields=["is_read"])
    return redirect("notifications_page")

@login_required
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect("notifications_page")

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Count, Q
from django.shortcuts import render
from accounts.models import UserProfile
from permissions.models import PermissionRequest, RequestHistory

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Count, Q
from django.shortcuts import render
from accounts.models import UserProfile
from permissions.models import PermissionRequest, RequestHistory

@login_required
def user_analytics(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    my_role = (profile.role or "").strip().lower() if profile else ""
    my_dept = profile.department if profile else None

    if my_role not in ("staff", "proctor", "hod", "dean", "principal"):
        return HttpResponseForbidden("Only authorities can access")

    search_type = (request.GET.get("type") or "").strip().lower()
    search_q = (request.GET.get("q") or "").strip()

    # -------------------------
    # ROLE BASED SEARCH RULES
    # -------------------------
    allowed_roles = []
    dept_filter_required = False

    if my_role in ("staff", "proctor"):
        allowed_roles = ["student"]
        dept_filter_required = True
    elif my_role == "hod":
        allowed_roles = ["student", "staff"]
        dept_filter_required = True
    elif my_role in ("dean", "principal"):
        allowed_roles = ["student", "staff", "proctor", "hod", "dean", "principal"]
        dept_filter_required = False

    # If user tries searching not allowed role
    if search_type and search_type not in allowed_roles:
        return HttpResponseForbidden(f"You are not allowed to search role: {search_type}")

    target_profile = None
    target_user = None

    submitted_qs = PermissionRequest.objects.none()
    received_qs = PermissionRequest.objects.none()
    submitted_counts = {}
    received_counts = {}
    action_counts = {}

    if search_type and search_q:
        prof_qs = UserProfile.objects.select_related("user").filter(role__iexact=search_type)

        # dept restriction (only staff/proctor/hod)
        if dept_filter_required:
            if not my_dept:
                return HttpResponseForbidden("Your department is not set.")
            prof_qs = prof_qs.filter(department=my_dept)

        prof_qs = prof_qs.filter(
            Q(user__username__icontains=search_q) |
            Q(user__first_name__icontains=search_q) |
            Q(user__last_name__icontains=search_q)
        )

        target_profile = prof_qs.first()
        if target_profile:
            target_user = target_profile.user

            submitted_qs = (
                PermissionRequest.objects
                .filter(student=target_user)
                .select_related("request_to", "student")
                .order_by("-applied_at")
            )

            received_qs = (
                PermissionRequest.objects
                .filter(request_to=target_user)
                .select_related("request_to", "student")
                .order_by("-applied_at")
            )

            # For dept restricted roles, also limit requests to same dept students
            if dept_filter_required and my_dept:
                submitted_qs = submitted_qs.filter(student__userprofile__department=my_dept)
                received_qs = received_qs.filter(student__userprofile__department=my_dept)

            submitted_counts = submitted_qs.aggregate(
                total=Count("id"),
                pending=Count("id", filter=Q(status__iexact="pending")),
                approved=Count("id", filter=Q(status__iexact="approved")),
                rejected=Count("id", filter=Q(status__iexact="rejected")),
                urgent=Count("id", filter=Q(is_urgent=True)),
            )

            received_counts = received_qs.aggregate(
                total=Count("id"),
                pending=Count("id", filter=Q(status__iexact="pending")),
                approved=Count("id", filter=Q(status__iexact="approved")),
                rejected=Count("id", filter=Q(status__iexact="rejected")),
                urgent=Count("id", filter=Q(is_urgent=True)),
            )

            action_counts = {
                "approved": RequestHistory.objects.filter(actor=target_user, action__iexact="approved").count(),
                "rejected": RequestHistory.objects.filter(actor=target_user, action__iexact="rejected").count(),
                "forwarded": RequestHistory.objects.filter(actor=target_user, action__iexact="forwarded").count(),
                "reassigned": RequestHistory.objects.filter(actor=target_user, action__iexact="reassigned").count(),
                "auto_escalated": RequestHistory.objects.filter(actor=target_user, action__iexact="auto_escalated").count(),
            }

    return render(request, "core/user_analytics.html", {
        "profile": profile,
        "dept": my_dept,

        "allowed_roles": allowed_roles,   # ✅ send to template dropdown
        "search_type": search_type,
        "search_q": search_q,

        "target_profile": target_profile,
        "target_user": target_user,
        "submitted_qs": submitted_qs,
        "received_qs": received_qs,
        "submitted_counts": submitted_counts,
        "received_counts": received_counts,
        "action_counts": action_counts,
    })