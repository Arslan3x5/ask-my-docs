from django.apps import AppConfig


class KnowledgeConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "knowledge"

    def ready(self):
        from django.conf import settings

        if getattr(settings, "OFFLINE_MODE", False):
            from .offline import install

            install(getattr(settings, "OFFLINE_ALLOW_HOSTS", []))