from django.contrib.auth.models import User
from django.db import models

class CalendarEvent(models.Model):
    TYPES = [("MEETING", "Meeting"), ("SPRINT", "Sprint"), ("HOLIDAY", "Holiday"), ("OTHER", "Other")]
    title = models.CharField(max_length=200)
    event_type = models.CharField(max_length=20, choices=TYPES, default="OTHER")
    start = models.DateTimeField()
    end = models.DateTimeField(null=True, blank=True)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)

    def __str__(self):
        return self.title
