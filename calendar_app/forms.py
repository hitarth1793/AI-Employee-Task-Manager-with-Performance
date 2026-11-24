from django import forms
from .models import CalendarEvent

class EventForm(forms.ModelForm):
    class Meta:
        model = CalendarEvent
        fields = ["title", "event_type", "start", "end", "description"]
        widgets = {
            "start": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "end": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start")
        end = cleaned_data.get("end")
        if start and end and end < start:
            self.add_error("end", "Event end must be at or after its start.")
        return cleaned_data
