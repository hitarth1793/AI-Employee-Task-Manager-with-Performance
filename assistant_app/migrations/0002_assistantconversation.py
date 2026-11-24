from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("assistant_app", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="AssistantConversation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(default="New conversation", max_length=120)),
                ("messages", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="assistant_conversations",
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={"ordering": ["-updated_at"]},
        ),
    ]
