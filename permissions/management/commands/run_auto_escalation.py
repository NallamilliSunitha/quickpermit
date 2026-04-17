# permissions/management/commands/runescalation.py
from django.core.management.base import BaseCommand
from permissions.utils import auto_escalate_permissions

class Command(BaseCommand):
    help = "Run auto escalation for urgent timed-out permission requests"

    def handle(self, *args, **kwargs):
        count = auto_escalate_permissions()
        self.stdout.write(self.style.SUCCESS(f"Done. Auto-escalated: {count}"))