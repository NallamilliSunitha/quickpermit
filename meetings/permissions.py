from accounts.models import UserProfile


def get_profile(user):
    return UserProfile.objects.filter(user=user).first()


def get_role(user):
    p = get_profile(user)
    return (p.role or "").strip().lower() if p else ""


def get_department(user):
    p = get_profile(user)
    return p.department if p else None


def can_create_meeting(user):
    # staff/proctor/hod/dean/principal can create
    return get_role(user) in ["staff", "proctor", "hod", "dean", "principal"]


def can_join_meeting(user):
    # any logged-in user can join if allowed by dept rules
    return get_role(user) in ["student", "staff", "proctor", "hod", "dean", "principal"]


def can_view_hod_dashboard(user):
    return get_role(user) in ["hod", "dean", "principal"]


def can_access_meeting(meeting, user):
    """
    dept rule:
    - dean/principal => can access any meeting
    - others => must match department
    """
    r = get_role(user)
    if r in ["dean", "principal"]:
        return True
    return (get_department(user) == meeting.department)