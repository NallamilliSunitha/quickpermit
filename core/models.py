

# Create your models here.
from django.db import models
from django.conf import settings

class Notification(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications")
    title = models.CharField(max_length=200)
    message = models.TextField(blank=True, default="")
    link = models.CharField(max_length=300, blank=True, default="")
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.user_id}: {self.title}"
class AcademicEvent(models.Model):
    department = models.CharField(max_length=100, blank=True, default="")
    title = models.CharField(max_length=200)
    event_date = models.DateField()
    is_blocked = models.BooleanField(default=False)

    class Meta:
        ordering = ["-event_date"]

    def __str__(self):
        return f"{self.department} {self.title} {self.event_date}"
