from django.views.decorators.http import require_POST

from apps.common.responses import not_implemented


@require_POST
def conversations(request):
    return not_implemented("learning.conversations")


@require_POST
def events(request):
    return not_implemented("learning.events")
