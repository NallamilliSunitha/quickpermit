from django.urls import path
from . import views

urlpatterns = [
    path('create/',                           views.create_meeting,           name='create_meeting'),
    path('detail/<int:id>/',                  views.meeting_detail,           name='meeting_detail'),
    path('history/',                          views.meeting_history,          name='meeting_history'),
    path('dashboard/',                        views.hod_meetings_dashboard,   name='hod_meetings_dashboard'),
    path('start/<int:id>/',                   views.start_meeting,            name='start_meeting'),
    path('join/<int:id>/',                    views.join_meeting,             name='join_meeting'),
    path('end/<int:id>/',                     views.end_meeting,              name='end_meeting'),
    path('cancel/<int:id>/',                  views.cancel_meeting,           name='cancel_meeting'),
    path('heartbeat/<int:id>/',               views.heartbeat,                name='meeting_heartbeat'),
    path('mark_left/<int:id>/',               views.mark_left,                name='mark_left'),
    path('live_attendance/<int:id>/',         views.live_attendance,          name='live_attendance'),
    path('status/<int:id>/',                  views.meeting_status,           name='meeting_status'),
    path('save_transcript/<int:id>/',         views.save_transcript,          name='save_transcript'),
    path('save_whiteboard/<int:id>/',         views.save_whiteboard,          name='save_whiteboard'),
    path('summary/<int:id>/',                 views.meeting_summary,          name='meeting_summary'),
    path('download_whiteboard_pdf/<int:id>/', views.download_whiteboard_pdf,  name='download_whiteboard_pdf'),
    path('download_attendance_pdf/<int:id>/', views.download_attendance_pdf,  name='download_attendance_pdf'),

]