from django.contrib import admin
from .models import Profile

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "department", "team", "job_title")
    list_filter = ("role", "department", "team")
    search_fields = ("user__username", "user__first_name", "user__last_name")
