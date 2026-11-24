from django import forms
from django.db.models import Q
from tasks.models import Task
from .models import Sprint

class SprintForm(forms.ModelForm):
    class Meta:
        model = Sprint
        fields = ["name", "goal", "start_date", "end_date", "tasks"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "goal": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            role = getattr(getattr(user, "profile", None), "role", "EMPLOYEE")
            tasks = Task.objects.all()
            if role == "MANAGER":
                department = getattr(user.profile, "department", "")
                tasks = tasks.filter(
                    Q(created_by=user)
                    | Q(assigned_to__profile__department=department)
                )
            self.fields["tasks"].queryset = tasks.distinct()

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "Sprint end date must not precede its start date.")
        return cleaned_data
