from django.contrib.auth.models import User
from django.db import models


class PerformanceReview(models.Model):
    CATEGORY_CHOICES = [
        ("POOR", "Poor"),
        ("AVERAGE", "Average"),
        ("GOOD", "Good"),
        ("EXCELLENT", "Excellent"),
    ]

    employee = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="performance_reviews"
    )
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="created_performance_reviews",
    )
    review_start = models.DateField()
    review_end = models.DateField()

    task_completion = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    on_time_delivery = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    attendance_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    leave_discipline = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    delayed_tasks = models.PositiveIntegerField(default=0)
    approved_leaves = models.PositiveIntegerField(default=0)
    unapproved_absences = models.PositiveIntegerField(default=0)
    overall_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default="AVERAGE")
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee.username} - {self.get_category_display()} ({self.review_start} to {self.review_end})"
