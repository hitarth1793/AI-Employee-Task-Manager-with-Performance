from django.contrib.auth.models import User
from django.db import models
from organization.models import Project

class Task(models.Model):
    PRIORITIES = [("LOW", "Low"), ("MEDIUM", "Medium"), ("HIGH", "High"), ("URGENT", "Urgent")]
    STATUSES = [("TODO", "To Do"), ("IN_PROGRESS", "In Progress"), ("REVIEW", "Review"), ("COMPLETED", "Completed")]

    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assigned_to = models.ForeignKey(User, on_delete=models.CASCADE, related_name="assigned_tasks")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="created_tasks")
    project = models.ForeignKey(
        Project, on_delete=models.SET_NULL, null=True, blank=True, related_name="tasks"
    )
    priority = models.CharField(max_length=20, choices=PRIORITIES, default="MEDIUM")
    status = models.CharField(max_length=20, choices=STATUSES, default="TODO")
    deadline = models.DateTimeField(null=True, blank=True)
    attachment = models.FileField(upload_to="task_attachments/", blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    @property
    def is_overdue(self):
        from django.utils import timezone
        return bool(self.deadline and self.deadline < timezone.now() and self.status != "COMPLETED")

class TaskComment(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="comments")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

class TaskHistory(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name="history")
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    action = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
