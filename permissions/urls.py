from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='permissions_index'),

    # 🔽 STAFF ACTIONS
    path('view/<int:id>/', views.view_request, name='view_request'),
    path('approve/<int:id>/', views.approve_request, name='approve_request'),
    path('reject/<int:id>/', views.reject_request, name='reject_request'),
    path('forward/<int:id>/', views.forward_request, name='forward_request'),

    path("requests/<int:pk>/forward-ui/", views.forward_ui, name="forward_ui"),
    path("requests/<int:pk>/forward-do/", views.forward_do, name="forward_do"),
    path("track/<int:id>/", views.track_request, name="track_request"),
    path("delete/<int:id>/", views.delete_request, name="delete_request"),
    path("bulk-forward/", views.bulk_forward_do, name="bulk_forward_do"),
    path("reassign/<int:pk>/", views.reassign_ui, name="reassign_ui"),
    path("reassign/<int:pk>/do/", views.reassign_do, name="reassign_do"),


    path("ai/insight/<int:pk>/", views.ai_insight_api, name="ai_insight_api"),
    path("ai/forward-suggestions/<int:pk>/", views.forward_suggestions_api, name="forward_suggestions_api"),
    path('ai/generate-letter/', views.generate_permission_letter, name='generate_permission_letter'),
    path("auto-escalate/", views.run_auto_escalation, name="auto_escalate"),
    path("request/<int:id>/", views.request_detail, name="request_detail"),
    path("send-reminders/", views.send_reminders_view, name="send_reminders"),]








