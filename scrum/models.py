from django.contrib.auth.models import User
from django.db import models
from tasks.models import Task

class Sprint(models.Model):
    name = models.CharField(max_length=150)
    goal = models.TextField(blank=True)
    start_date = models.DateField()
    end_date = models.DateField()
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    tasks = models.ManyToManyField(Task, blank=True, related_name="sprints")
    closed = models.BooleanField(default=False)

    def __str__(self):
        return self.name

    @property
    def completion_percent(self):
        total = self.tasks.count()
        if not total:
            return 0
        completed = self.tasks.filter(status="COMPLETED").count()
        return int(completed * 100 / total)
