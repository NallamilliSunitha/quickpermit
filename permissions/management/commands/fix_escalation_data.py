from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from permissions.models import PermissionRequest
from accounts.models import UserProfile


class Command(BaseCommand):
    help = "Fix pending requests data so auto-escalation can work (current_level/escalate_at)."

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=60, help="Default minutes to set escalate_at in future if missing.")
        parser.add_argument("--dry-run", action="store_true", help="Show changes but do not save.")

    def handle(self, *args, **options):
        now = timezone.now()
        minutes = options["minutes"]
        dry = options["dry_run"]

        fixed_level = 0
        fixed_escalate_at = 0
        skipped_no_profile = 0

        qs = PermissionRequest.objects.filter(status__iexact="pending").select_related("request_to")

        for req in qs:
            changed_fields = []

            # 1) Fix current_level from request_to's UserProfile role
            if req.request_to_id:
                prof = UserProfile.objects.filter(user=req.request_to).first()
                if prof and prof.role:
                    role = prof.role.strip().lower()
                    if (req.current_level or "").strip().lower() != role:
                        req.current_level = role
                        changed_fields.append("current_level")
                        fixed_level += 1
                else:
                    skipped_no_profile += 1

            # 2) Ensure escalate_at exists for pending requests (so scheduler has something to trigger)
            if req.escalate_at is None:
                req.escalate_at = now + timedelta(minutes=minutes)
                changed_fields.append("escalate_at")
                fixed_escalate_at += 1

            # 3) If it’s already past but current_level is principal, push it forward so it can re-run later
            # (No escalation possible at principal)
            if (req.current_level or "").strip().lower() == "principal":
                # move it 10 minutes ahead to avoid constant "due" stuck records
                req.escalate_at = now + timedelta(minutes=10)
                if "escalate_at" not in changed_fields:
                    changed_fields.append("escalate_at")

            if changed_fields:
                if dry:
                    self.stdout.write(f"[DRY] req={req.id} updated: {', '.join(changed_fields)}")
                else:
                    req.save(update_fields=changed_fields)

        self.stdout.write(self.style.SUCCESS(
            f"Done. Fixed current_level: {fixed_level}, set escalate_at: {fixed_escalate_at}, skipped(no profile): {skipped_no_profile}"
        ))
