from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('student', 'Student'),
        ('staff', 'Staff'),
        ('hod', 'HOD'),
        ('dean', 'Dean'),
        ('principal', 'Principal'),
    ]

    DEPARTMENT_CHOICES = [
        ('CSE',  'Computer Science'),
        ('ECE',  'Electronics'),
        ('AIML', 'AI & Machine Learning'),
        ('IT',   'Information Technology'),
        ('CIVIL','Civil Engineering'),
        ('MECH', 'Mechanical Engineering'),
        ('EEE',  'Electrical Engineering'),
    ]

    DEAN_TYPE_CHOICES = [
        ('Academic Affairs', 'Academic Affairs'),
        ('R&D', 'R&D'),
        ('Student Affairs', 'Student Affairs'),
        ('Placements', 'Placements'),
    ]

    COLLEGE_CHOICES = [
        ('Aditya University', 'Aditya University'),
        ('Aditya College of Engineering and Technology', 'Aditya College of Engineering and Technology'),
        ('Aditya College of Engineering', 'Aditya College of Engineering'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, blank=True, null=True)
    dean_type = models.CharField(max_length=50, choices=DEAN_TYPE_CHOICES, blank=True, null=True)

    roll_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    semester = models.CharField(max_length=2, blank=True, null=True)
    college = models.CharField(max_length=100, choices=COLLEGE_CHOICES, blank=True, null=True)  # ✅ New field

    is_approved = models.BooleanField(default=True)
    parent_email = models.EmailField(blank=True, null=True)
    photo = models.ImageField(upload_to="profile_photos/", null=True, blank=True)
    signature = models.ImageField(upload_to="signatures/", null=True, blank=True)
    stamp = models.ImageField(upload_to="stamps/", null=True, blank=True)
    designation = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.role}"


# ---------------- PASSWORD RESET ---------------- #

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(default=timezone.now)

    def is_expired(self):
        return timezone.now() > self.created_at + timezone.timedelta(minutes=5)

    def __str__(self):
        return f"{self.user.username} - OTP"