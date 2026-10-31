from django.urls import path

from . import views

app_name = "model_gateway"
urlpatterns = [path("chat/", views.chat, name="chat")]
