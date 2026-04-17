from django.urls import path
from . import views

urlpatterns = [
    path("subjects/",                  views.subject_list,    name="subject_list"),
    path("subjects/add/",              views.add_subject,     name="add_subject"),
    path("subjects/delete/<int:pk>/",  views.delete_subject,  name="delete_subject"),
    path("enter/<int:subject_id>/",    views.enter_marks,     name="enter_marks"),
    path("analytics/",                 views.marks_analytics, name="marks_analytics"),
    path("my/",                        views.student_marks,   name="student_marks"),
]