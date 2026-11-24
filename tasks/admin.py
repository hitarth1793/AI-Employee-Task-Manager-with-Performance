from django.contrib import admin
from .models import Task, TaskComment, TaskHistory

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "assigned_to", "priority", "status", "deadline")
    list_filter = ("priority", "status")
    search_fields = ("title", "description", "assigned_to__username")

admin.site.register(TaskComment)
admin.site.register(TaskHistory)
