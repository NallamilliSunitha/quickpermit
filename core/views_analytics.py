from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.db.models import Count, Q
from django.shortcuts import render
from django.utils import timezone

from accounts.models import UserProfile
from permissions.models import PermissionRequest, RequestHistory


@login_required
def analytics_dashboard(request):
    profile = UserProfile.objects.filter(user=request.user).first()
    role = (profile.role or "").strip().lower() if profile else ""
    if role not in ("staff", "proctor", "hod", "dean", "principal"):
        return HttpResponseForbidden("Only authorities can access")

    dept = profile.department if profile else None
    now = timezone.now()

    # -------------------------
    # Department wise (existing)
    # -------------------------
    qs = PermissionRequest.objects.select_related("student").all()
    if dept:
        qs = qs.filter(student__userprofile__department=dept)

    top_students = (
        qs.values("student__username")
        .annotate(
            total=Count("id"),
            urgent=Count("id", filter=Q(is_urgent=True)),
            approved=Count("id", filter=Q(status__iexact="approved")),
            rejected=Count("id", filter=Q(status__iexact="rejected")),
        )
        .order_by("-total")[:10]
    )

    summary = qs.aggregate(
        total=Count("id"),
        pending=Count("id", filter=Q(status__iexact="pending")),
        urgent_pending=Count("id", filter=Q(status__iexact="pending", is_urgent=True)),
        approvals=Count("id", filter=Q(status__iexact="approved")),
        rejections=Count("id", filter=Q(status__iexact="rejected")),
    )

    # -------------------------
    # Search analytics (NEW)
    # -------------------------
    search_type = (request.GET.get("type") or "").strip().lower()
    search_q = (request.GET.get("q") or "").strip()

    target_profile = None
    target_user = None

    submitted_qs = PermissionRequest.objects.none()
    received_qs = PermissionRequest.objects.none()
    submitted_counts = {
        "total": 0, "pending": 0, "approved": 0, "rejected": 0, "urgent": 0
    }
    received_counts = {
        "total": 0, "pending": 0, "approved": 0, "rejected": 0, "urgent": 0
    }
    action_counts = {
        "approved": 0,
        "rejected": 0,
        "forwarded": 0,
        "reassigned": 0,
        "auto_escalated": 0,
    }

    if search_type and search_q:
        prof_qs = UserProfile.objects.select_related("user").filter(role__iexact=search_type)
        if dept:
            prof_qs = prof_qs.filter(department=dept)

        prof_qs = prof_qs.filter(
            Q(user__username__icontains=search_q) |
            Q(user__first_name__icontains=search_q) |
            Q(user__last_name__icontains=search_q)
        )

        target_profile = prof_qs.first()
        if target_profile:
            target_user = target_profile.user

            # A) Submitted
            submitted_qs = (
                PermissionRequest.objects
                .select_related("request_to", "student")
                .filter(student=target_user)
                .order_by("-applied_at")
            )
            if dept:
                submitted_qs = submitted_qs.filter(student__userprofile__department=dept)

            submitted_counts = submitted_qs.aggregate(
                total=Count("id"),
                pending=Count("id", filter=Q(status__iexact="pending")),
                approved=Count("id", filter=Q(status__iexact="approved")),
                rejected=Count("id", filter=Q(status__iexact="rejected")),
                urgent=Count("id", filter=Q(is_urgent=True)),
            )

            # B) Received
            received_qs = (
                PermissionRequest.objects
                .select_related("request_to", "student")
                .filter(request_to=target_user)
                .order_by("-applied_at")
            )
            if dept:
                received_qs = received_qs.filter(student__userprofile__department=dept)

            received_counts = received_qs.aggregate(
                total=Count("id"),
                pending=Count("id", filter=Q(status__iexact="pending")),
                approved=Count("id", filter=Q(status__iexact="approved")),
                rejected=Count("id", filter=Q(status__iexact="rejected")),
                urgent=Count("id", filter=Q(is_urgent=True)),
            )

            # C) Actions done by this user (history)
            action_counts = {
                "approved": RequestHistory.objects.filter(actor=target_user, action__iexact="approved").count(),
                "rejected": RequestHistory.objects.filter(actor=target_user, action__iexact="rejected").count(),

                # some projects store "forward" instead of "forwarded"
                "forwarded": RequestHistory.objects.filter(
                    actor=target_user,
                    action__in=["forwarded", "forward"]
                ).count(),

                # some projects store "reassign" instead of "reassigned"
                "reassigned": RequestHistory.objects.filter(
                    actor=target_user,
                    action__in=["reassigned", "reassign"]
                ).count(),

                # auto escalations RECEIVED by this user (actor is usually None)
                "auto_escalated": RequestHistory.objects.filter(
                    action__iexact="auto_escalated",
                    request__request_to=target_user
                ).count(),
            }

    return render(request, "core/analytics.html", {
        "profile": profile,
        "now": now,

        # department
        "summary": summary,
        "top_students": top_students,

        # search context
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