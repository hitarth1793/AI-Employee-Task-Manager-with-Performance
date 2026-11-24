from django.contrib import admin

from .models import PerformanceReview


@admin.register(PerformanceReview)
class PerformanceReviewAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "category",
        "overall_score",
        "review_start",
        "review_end",
        "reviewed_by",
        "created_at",
    )
    list_filter = ("category", "review_start", "review_end")
    search_fields = ("employee__username", "employee__first_name", "employee__last_name")
    readonly_fields = (
        "task_completion",
        "on_time_delivery",
        "attendance_score",
        "leave_discipline",
        "delayed_tasks",
        "approved_leaves",
        "unapproved_absences",
        "overall_score",
        "category",
        "created_at",
    )
