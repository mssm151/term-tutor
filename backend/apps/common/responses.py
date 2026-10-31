from django.http import JsonResponse


def not_implemented(module):
    """Make unimplemented integrations explicit instead of faking success."""
    return JsonResponse(
        {
            "error": {
                "code": "NOT_IMPLEMENTED",
                "module": module,
                "message": "仅提供项目框架，此业务接口尚未实现。",
            }
        },
        status=501,
        json_dumps_params={"ensure_ascii": False},
    )
