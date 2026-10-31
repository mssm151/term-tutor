from django.views.decorators.http import require_POST

from apps.common.responses import not_implemented


@require_POST
def search(request):
    return not_implemented("knowledge.search")
