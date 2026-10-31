from django.apps import AppConfig


class ModelGatewayConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.model_gateway"
    verbose_name = "模型网关"
