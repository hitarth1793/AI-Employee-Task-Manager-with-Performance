from django import forms
from django.utils import timezone

from .models import PerformanceReview


class PerformanceReviewForm(forms.ModelForm):
    category = forms.ChoiceField(
        choices=[("", "Automatic (calculated)"), *PerformanceReview.CATEGORY_CHOICES],
        required=False,
        label="Admin rating",
    )

    class Meta:
        model = PerformanceReview
        fields = ["review_start", "review_end", "category", "comment"]
        widgets = {
            "review_start": forms.DateInput(attrs={"type": "date"}),
            "review_end": forms.DateInput(attrs={"type": "date"}),
            "comment": forms.Textarea(
                attrs={
                    "rows": 5,
                    "placeholder": "Add an optional Admin performance review comment...",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        today = timezone.localdate()
        self.fields["review_start"].initial = today.replace(day=1)
        self.fields["review_end"].initial = today

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("review_start")
        end = cleaned.get("review_end")
        if start and end and start > end:
            raise forms.ValidationError("Review start date must be before the end date.")
        return cleaned
