
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="LeaveBalance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("casual_balance", models.PositiveIntegerField(default=5)),
                ("sick_balance", models.PositiveIntegerField(default=3)),
                ("earned_balance", models.PositiveIntegerField(default=12)),
                ("user", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="leave_balance", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="LeaveRequest",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("leave_type", models.CharField(choices=[("CASUAL","Casual"),("SICK","Sick"),("EARNED","Earned")], max_length=20)),
                ("start_date", models.DateField()),
                ("end_date", models.DateField()),
                ("reason", models.TextField(blank=True)),
                ("status", models.CharField(choices=[("PENDING","Pending"),("APPROVED","Approved"),("REJECTED","Rejected")], default="PENDING", max_length=20)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="reviewed_leaves", to=settings.AUTH_USER_MODEL)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="leave_requests", to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name="Attendance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("date", models.DateField()),
                ("status", models.CharField(choices=[("PRESENT","Present"),("ABSENT","Absent"),("WFH","Work From Home"),("LEAVE","Leave")], default="PRESENT", max_length=20)),
                ("check_in", models.TimeField(blank=True, null=True)),
                ("check_out", models.TimeField(blank=True, null=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="attendance", to=settings.AUTH_USER_MODEL)),
            ],
            options={"unique_together": {("user", "date")}},
        ),
    ]
