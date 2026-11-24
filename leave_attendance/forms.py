from django import forms
from django.core.exceptions import ValidationError
from .models import Attendance, LeaveRequest

class LeaveForm(forms.ModelForm):
    class Meta:
        model = LeaveRequest
        fields = ["leave_type", "start_date", "end_date", "reason"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "reason": forms.Textarea(attrs={"rows": 3}),
        }

    def clean(self):
        cleaned = super().clean()
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        if start_date and end_date and end_date < start_date:
            raise ValidationError("Leave end date cannot be before the start date.")
        return cleaned

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ["user", "date", "status", "check_in", "check_out"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "check_in": forms.TimeInput(attrs={"type": "time"}),
            "check_out": forms.TimeInput(attrs={"type": "time"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user and getattr(getattr(user, "profile", None), "role", "") == "MANAGER":
            self.fields["user"].queryset = self.fields["user"].queryset.filter(
                profile__department=user.profile.department
            )

    def clean(self):
        cleaned = super().clean()
        check_in = cleaned.get("check_in")
        check_out = cleaned.get("check_out")
        if check_in and check_out and check_out < check_in:
            self.add_error("check_out", "Check-out must not be earlier than check-in.")
        return cleaned
