from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import PermissionRequest, PermissionAIInsight
from .ai import compute_permission_insight

@receiver(post_save, sender=PermissionRequest)
def update_ai_insight(sender, instance, created, **kwargs):
    # compute only for pending or whenever you want
    data = compute_permission_insight(instance)

    obj, _ = PermissionAIInsight.objects.get_or_create(request=instance)
    obj.score = data["score"]
    obj.recommendation = data["recommendation"]
    obj.flags = ", ".join(data["flags"])
    obj.summary = data["summary"]
    obj.version = "rule-v1"
    obj.save()
