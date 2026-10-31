from django.urls import path

from . import views

app_name = "learning"
urlpatterns = [
    path("conversations/", views.conversations, name="conversations"),
    path("events/", views.events, name="events"),
]
