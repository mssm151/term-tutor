from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_GET


@require_GET
def index(request):
    return JsonResponse(
        {
            "project": "terminal-tutor",
            "stage": "framework-only",
            "message": "Django 框架已建立；Agent、SSH、串口、RAG 与模型尚未实现。",
            "links": {"health": reverse("health"), "admin": reverse("admin:index")},
        },
        json_dumps_params={"ensure_ascii": False},
    )


@require_GET
def health(request):
    """Liveness only; no external dependency or target-machine checks."""
    return JsonResponse(
        {"status": "ok", "service": "terminal-tutor-backend", "mode": "framework-only"}
    )
