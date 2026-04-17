from django.apps import AppConfig
import os

class PermissionsConfig(AppConfig):
    name = "permissions"

    def ready(self):
        # Prevent running twice with Django auto-reloader
        if os.environ.get("RUN_MAIN") == "true":
            from permissions.scheduler import start
            start()