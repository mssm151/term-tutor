from django.views.decorators.http import require_GET

from apps.common.responses import not_implemented


@require_GET
def course_list(request):
    return not_implemented("courses.list")


@require_GET
def task_list(request, course_id):
    return not_implemented("courses.tasks")
