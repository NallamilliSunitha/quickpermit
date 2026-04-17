from django.db.models import Count, Q
from accounts.models import UserProfile
from permissions.models import PermissionRequest

ROLE_FLOW = {
    "student": ["proctor", "staff", "hod", "dean", "principal"],
    "proctor": ["hod", "dean", "principal"],
    "staff": ["hod", "dean", "principal"],
    "hod": ["dean", "principal"],
    "dean": ["principal"],
    "principal": [],
}

def suggest_forward_targets(current_user, req):
    """
    Suggest next authority users in same department based on lowest pending load.
    Returns list of dicts: {id, name, role, pending_count}
    """
    my_profile = UserProfile.objects.filter(user=current_user).first()
    if not my_profile:
        return []

    my_role = (my_profile.role or "").strip().lower()
    dept = my_profile.department

    allowed_roles = ROLE_FLOW.get(my_role, [])
    if not allowed_roles:
        return []

    qs = UserProfile.objects.filter(
        department=dept,
        role__in=allowed_roles
    ).select_related("user")

    suggestions = []
    for p in qs:
        pending_load = PermissionRequest.objects.filter(
            request_to=p.user,
            status="pending"
        ).count()

        full = (p.user.get_full_name() or "").strip()
        name = full if full else p.user.username

        suggestions.append({
            "id": p.user.id,
            "name": name,
            "role": p.role,
            "pending_count": pending_load
        })

    # sort: least pending first
    suggestions.sort(key=lambda x: x["pending_count"])
    return suggestions[:5]  # top 5
