from django.contrib.auth.models import User
from django.db import models

class Profile(models.Model):
    ROLE_CHOICES = [
        ("ADMIN", "Admin"),
        ("MANAGER", "Manager"),
        ("EMPLOYEE", "Employee"),
    ]
    PERFORMANCE_CATEGORY_CHOICES = [
        ("POOR", "Poor"),
        ("AVERAGE", "Average"),
        ("GOOD", "Good"),
        ("EXCELLENT", "Excellent"),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="EMPLOYEE")
    department = models.CharField(max_length=100, blank=True)
    team = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    job_title = models.CharField(max_length=100, blank=True)
    joined_date = models.DateField(null=True, blank=True)
    manual_performance_category = models.CharField(
        max_length=20,
        choices=PERFORMANCE_CATEGORY_CHOICES,
        blank=True,
        default="",
    )

    def __str__(self):
        return f"{self.user.username} - {self.role}"

    @property
    def display_name(self):
        return self.user.get_full_name() or self.user.username
