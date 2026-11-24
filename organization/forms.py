from django import forms
from django.contrib.auth.models import User

from .models import Department, Project, Team


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description"]


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name", "department", "members"]
        widgets = {"members": forms.CheckboxSelectMultiple}

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["members"].queryset = User.objects.filter(
            is_active=True, profile__role="EMPLOYEE"
        ).order_by("first_name", "username")
        self.fields["members"].required = False
        if user and user.profile.role == "MANAGER":
            self.fields["department"].queryset = Department.objects.filter(
                name=user.profile.department
            )


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ["name", "description", "team", "start_date", "end_date", "status"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        teams = Team.objects.select_related("department")
        if user and user.profile.role == "MANAGER":
            teams = teams.filter(department__name=user.profile.department)
        self.fields["team"].queryset = teams

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("start_date")
        end = cleaned.get("end_date")
        if start and end and end < start:
            self.add_error("end_date", "End date cannot be before start date.")
        return cleaned
