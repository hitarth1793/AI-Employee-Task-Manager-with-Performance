from django import forms
from django.contrib.auth.models import User
from organization.models import Project
from .models import Task, TaskComment

class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ["title", "description", "assigned_to", "project", "priority", "status", "deadline", "attachment"]
        widgets = {
            "deadline": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "description": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        assignees = User.objects.filter(
            is_active=True, profile__role="EMPLOYEE"
        )
        if user and user.profile.role == "MANAGER":
            assignees = assignees.filter(profile__department=user.profile.department)
        self.fields["assigned_to"].queryset = assignees.order_by("first_name")
        projects = Project.objects.filter(status="ACTIVE").select_related("team", "team__department")
        if user and user.profile.role == "MANAGER":
            projects = projects.filter(team__department__name=user.profile.department)
        elif user and user.profile.role == "EMPLOYEE":
            projects = projects.filter(team__members=user)
        self.fields["project"].queryset = projects.distinct()

class CommentForm(forms.ModelForm):
    class Meta:
        model = TaskComment
        fields = ["comment"]
        widgets = {"comment": forms.Textarea(attrs={"rows": 2, "placeholder": "Write a comment..."})}
