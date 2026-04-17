from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Meeting(models.Model):
    AUDIENCE_CHOICES = (
        ("students", "Students"),
        ("staff", "Staff"),
        ("both", "Both"),
        ("hod", "HOD"),
        ("dean", "Dean"),
        ("all", "All"),
    )
    STATUS_CHOICES = (
        ("scheduled", "Scheduled"),
        ("ongoing", "Ongoing"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    )
    title = models.CharField(max_length=255)
    meeting_type = models.CharField(max_length=30, default="general")
    department = models.CharField(max_length=50, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name="meetings_created")
    room_name = models.CharField(max_length=100, unique=True)
    scheduled_at = models.DateTimeField(blank=True, null=True)
    duration_minutes = models.IntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(blank=True, null=True)
    ended_at = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    audience_type = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default="students")
    notes = models.TextField(blank=True, null=True)
    cancel_comment = models.TextField(blank=True, null=True)
    summary = models.TextField(blank=True, null=True)
    ai_summary = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.title


class MeetingRecipient(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="recipients")
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("meeting", "user")

    def __str__(self):
        return f"{self.user.username} -> {self.meeting.title}"


class MeetingParticipant(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="participants")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(blank=True, null=True)
    left_at = models.DateTimeField(blank=True, null=True)
    participation_score = models.FloatField(default=0)
    messages_count = models.IntegerField(default=0)
    last_seen = models.DateTimeField(blank=True, null=True)
    left_early = models.BooleanField(default=False)   # NEW

    class Meta:
        unique_together = ("meeting", "user")

    def mark_join(self):
        if not self.joined_at:
            self.joined_at = timezone.now()
        self.last_seen = timezone.now()
        self.save(update_fields=["joined_at", "last_seen"])

    def touch(self):
        self.last_seen = timezone.now()
        self.save(update_fields=["last_seen"])

    def __str__(self):
        return f"{self.user.username} joined {self.meeting.title}"


class MeetingCheckpoint(models.Model):
    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name="checkpoints")
    checkpoint_no = models.PositiveSmallIntegerField()
    scheduled_at = models.DateTimeField()

    class Meta:
        unique_together = ("meeting", "checkpoint_no")
        ordering = ["checkpoint_no"]

    def __str__(self):
        return f"{self.meeting.title} - Checkpoint {self.checkpoint_no}"


class CheckpointPresence(models.Model):
    checkpoint = models.ForeignKey(MeetingCheckpoint, on_delete=models.CASCADE, related_name="presences")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    present = models.BooleanField(default=False)
    marked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("checkpoint", "user")

    def __str__(self):
        return f"{self.user.username} - CP{self.checkpoint.checkpoint_no} - {self.present}"


# NEW
class MeetingTranscript(models.Model):
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name="transcript")
    content = models.TextField(default="[]")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Transcript: {self.meeting.title}"


# NEW
class MeetingWhiteboard(models.Model):
    meeting = models.OneToOneField(Meeting, on_delete=models.CASCADE, related_name="whiteboard")
    image_data = models.TextField(default="")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Whiteboard: {self.meeting.title}"