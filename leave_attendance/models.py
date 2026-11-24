from django.contrib.auth.models import User
from django.db import models

class LeaveBalance(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="leave_balance")
    casual_balance = models.PositiveIntegerField(default=5)
    sick_balance = models.PositiveIntegerField(default=3)
    earned_balance = models.PositiveIntegerField(default=12)

class LeaveRequest(models.Model):
    TYPES = [("CASUAL", "Casual"), ("SICK", "Sick"), ("EARNED", "Earned")]
    STATUS = [("PENDING", "Pending"), ("APPROVED", "Approved"), ("REJECTED", "Rejected")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="leave_requests")
    leave_type = models.CharField(max_length=20, choices=TYPES)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS, default="PENDING")
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="reviewed_leaves")
    created_at = models.DateTimeField(auto_now_add=True)

class Attendance(models.Model):
    STATUS = [("PRESENT", "Present"), ("ABSENT", "Absent"), ("WFH", "Work From Home"), ("LEAVE", "Leave")]
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="attendance")
    date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS, default="PRESENT")
    check_in = models.TimeField(null=True, blank=True)
    check_out = models.TimeField(null=True, blank=True)

    class Meta:
        unique_together = ("user", "date")
