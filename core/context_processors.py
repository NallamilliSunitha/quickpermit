from core.models import Notification

def notifications_context(request):
    if request.user.is_authenticated:
        unread = Notification.objects.filter(
            user=request.user,
            is_read=False
        ).order_by("-created_at")[:5]

        return {
            "nav_unread_count": unread.count(),
            "nav_notifications": unread
        }

    return {
        "nav_unread_count": 0,
        "nav_notifications": []
    }