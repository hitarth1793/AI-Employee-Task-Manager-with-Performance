
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="CalendarEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("event_type", models.CharField(choices=[("MEETING","Meeting"),("SPRINT","Sprint"),("HOLIDAY","Holiday"),("OTHER","Other")], default="OTHER", max_length=20)),
                ("start", models.DateTimeField()),
                ("end", models.DateTimeField(blank=True, null=True)),
                ("description", models.TextField(blank=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]
