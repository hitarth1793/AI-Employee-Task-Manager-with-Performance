from django.contrib.auth.models import User
from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Team(models.Model):
    name = models.CharField(max_length=100)
    department = models.ForeignKey(
        Department, on_delete=models.PROTECT, related_name="teams"
    )
    members = models.ManyToManyField(User, blank=True, related_name="managed_teams")

    class Meta:
        ordering = ["department__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["department", "name"], name="unique_team_name_per_department"
            )
        ]

    def __str__(self):
        return f"{self.department.name} / {self.name}"


class Project(models.Model):
    STATUS_CHOICES = [("ACTIVE", "Active"), ("ARCHIVED", "Archived")]

    name = models.CharField(max_length=150, unique=True)
    description = models.TextField(blank=True)
    team = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="projects")
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    created_by = models.ForeignKey(
        User, on_delete=models.PROTECT, related_name="created_projects"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValidationError({"end_date": "End date cannot be before start date."})

    def __str__(self):
        return self.name
