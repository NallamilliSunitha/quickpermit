from django.db import models

# Create your models here.
from django.db import models
from django.contrib.auth.models import User

SEMESTER_CHOICES = [(str(i), f"Semester {i}") for i in range(1, 9)]

EXAM_TYPE_CHOICES = [
    ("mid1", "Mid 1"),
    ("mid2", "Mid 2"),
    ("lab", "Lab"),
]


class Subject(models.Model):
    name       = models.CharField(max_length=100)
    code       = models.CharField(max_length=20, blank=True)
    department = models.CharField(max_length=100)
    semester   = models.CharField(max_length=2, choices=SEMESTER_CHOICES)
    staff      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="subjects")
    is_lab     = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("name", "department", "semester")
        ordering = ["semester", "name"]

    def __str__(self):
        return f"{self.name} (Sem {self.semester} - {self.department})"


class StudentMark(models.Model):
    student    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="marks")
    subject    = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name="marks")
    exam_type  = models.CharField(max_length=10, choices=EXAM_TYPE_CHOICES)
    entered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="entered_marks")
    updated_at = models.DateTimeField(auto_now=True)

    # Theory marks (Mid1 / Mid2)
    objective   = models.FloatField(null=True, blank=True)   # max 10
    descriptive = models.FloatField(null=True, blank=True)   # max 15
    assignment  = models.FloatField(null=True, blank=True)   # max 5

    # Lab marks
    lab_internal = models.FloatField(null=True, blank=True)  # max 30
    lab_external = models.FloatField(null=True, blank=True)  # max 70

    class Meta:
        unique_together = ("student", "subject", "exam_type")

    def theory_total(self):
        return (self.objective or 0) + (self.descriptive or 0) + (self.assignment or 0)

    def lab_total(self):
        return (self.lab_internal or 0) + (self.lab_external or 0)

    def total(self):
        if self.subject.is_lab:
            return self.lab_total()
        return self.theory_total()

    def passed(self):
        if self.exam_type == "lab":
            internal_pass = (self.lab_internal or 0) >= 12
            external_pass = (self.lab_external or 0) >= 28
            return internal_pass and external_pass
        else:
            return self.theory_total() >= 12

    def __str__(self):
        return f"{self.student.username} - {self.subject.name} - {self.exam_type}"