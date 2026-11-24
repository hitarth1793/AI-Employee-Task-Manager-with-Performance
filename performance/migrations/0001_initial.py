from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]
    operations = [
        migrations.CreateModel(
            name="PerformanceReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("review_start", models.DateField()),
                ("review_end", models.DateField()),
                ("task_completion", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("on_time_delivery", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("attendance_score", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("leave_discipline", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("delayed_tasks", models.PositiveIntegerField(default=0)),
                ("approved_leaves", models.PositiveIntegerField(default=0)),
                ("unapproved_absences", models.PositiveIntegerField(default=0)),
                ("overall_score", models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ("category", models.CharField(choices=[("POOR", "Poor"), ("AVERAGE", "Average"), ("GOOD", "Good"), ("EXCELLENT", "Excellent")], default="AVERAGE", max_length=20)),
                ("comment", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("employee", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="performance_reviews", to=settings.AUTH_USER_MODEL)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_performance_reviews", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
