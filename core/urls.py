from django.urls import path
from core import views
from .views_analytics import analytics_dashboard
from .views_reports import permission_report_pdf

from .views import user_analytics
urlpatterns = [
    path("notifications/", views.notifications_page, name="notifications_page"),
    path("notifications/api/", views.notifications_api, name="notifications_api"),
    path("notifications/read/<int:pk>/", views.mark_read, name="notification_mark_read"),
    path("notifications/read-all/", views.mark_all_read, name="notification_mark_all_read"),

    path("analytics/", analytics_dashboard, name="analytics_dashboard"),
    path("reports/permissions.pdf", permission_report_pdf, name="permission_report_pdf"),

    path("user-analytics/", user_analytics, name="user_analytics"),

]
