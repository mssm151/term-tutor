from django.urls import path

from . import views

app_name = "knowledge"
urlpatterns = [path("search/", views.search, name="search")]
