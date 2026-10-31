from django.views.decorators.http import require_POST

from apps.common.responses import not_implemented


@require_POST
def chat(request):
    return not_implemented("model_gateway.chat")
