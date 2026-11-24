from django.contrib import admin
from .models import Sprint

@admin.register(Sprint)
class SprintAdmin(admin.ModelAdmin):
    list_display = ("name", "start_date", "end_date", "closed")
    filter_horizontal = ("tasks",)
