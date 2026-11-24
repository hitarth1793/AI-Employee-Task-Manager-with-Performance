import uuid

from django.contrib.auth.models import User
from django.db import models


class AssistantConversation(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assistant_conversations"
    )
    title = models.CharField(max_length=120, default="New conversation")
    messages = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class AuthorizedAction(models.Model):
    ACTION_TYPES = [
        ("CREATE_TASK", "Create task"),
        ("REQUEST_LEAVE", "Request leave"),
        ("APPROVE_LEAVE", "Approve leave"),
    ]
    STATUSES = [
        ("PENDING", "Pending confirmation"),
        ("COMPLETED", "Completed"),
        ("CANCELLED", "Cancelled"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="assistant_actions"
    )
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    action_type = models.CharField(max_length=30, choices=ACTION_TYPES)
    payload = models.JSONField()
    status = models.CharField(max_length=20, choices=STATUSES, default="PENDING")
    result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_action_type_display()} ({self.status})"
