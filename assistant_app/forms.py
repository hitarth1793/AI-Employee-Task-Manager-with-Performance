from django import forms
from django.contrib.auth.models import User

from leave_attendance.models import LeaveRequest
from organization.models import Project
from tasks.models import Task


class TaskActionForm(forms.Form):
    title = forms.CharField(max_length=200)
    description = forms.CharField(required=False, widget=forms.Textarea)
    assigned_to = forms.ModelChoiceField(queryset=User.objects.none())
    project = forms.ModelChoiceField(queryset=Project.objects.none(), required=False)
    priority = forms.ChoiceField(choices=Task.PRIORITIES)
    deadline = forms.DateTimeField(required=False, input_formats=["%Y-%m-%dT%H:%M"])

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = User.objects.filter(
            is_active=True, profile__role="EMPLOYEE"
        ).order_by("first_name", "username")
        projects = Project.objects.filter(status="ACTIVE")
        if user.profile.role == "MANAGER":
            projects = projects.filter(team__department__name=user.profile.department)
        self.fields["project"].queryset = projects


class LeaveActionForm(forms.Form):
    leave_type = forms.ChoiceField(choices=LeaveRequest.TYPES)
    start_date = forms.DateField(input_formats=["%Y-%m-%d"])
    end_date = forms.DateField(input_formats=["%Y-%m-%d"])
    reason = forms.CharField(required=False, widget=forms.Textarea)

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("start_date"), cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "Leave end date cannot be before its start date.")
        return cleaned


class LeaveApprovalActionForm(forms.Form):
    leave = forms.ModelChoiceField(queryset=LeaveRequest.objects.none())

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        leaves = LeaveRequest.objects.filter(status="PENDING").select_related("user__profile")
        if user.profile.role == "MANAGER":
            leaves = leaves.filter(user__profile__department=user.profile.department)
        self.fields["leave"].queryset = leaves.exclude(user=user)
