from django.urls import path

from . import views

app_name = "courses"
urlpatterns = [
    path("", views.course_list, name="list"),
    path("<int:course_id>/tasks/", views.task_list, name="tasks"),
]
