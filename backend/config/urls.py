from django.contrib import admin
from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("admin/", admin.site.urls),
    path("api/health/", views.health, name="health"),
    path("api/auth/", include("apps.accounts.urls")),
    path("api/courses/", include("apps.courses.urls")),
    path("api/knowledge/", include("apps.knowledge.urls")),
    path("api/learning/", include("apps.learning.urls")),
    path("api/model/", include("apps.model_gateway.urls")),
]
