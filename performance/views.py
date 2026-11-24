from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render


from .forms import PerformanceReviewForm
from .models import PerformanceReview
from .services import calculate_performance


def _is_admin(request):
    return getattr(getattr(request.user, "profile", None), "role", "") == "ADMIN"


def _current_period():
    today = datetime.now().date()
    return today.replace(day=1), today


@login_required
def performance_list(request):
    if not _is_admin(request):
        return redirect("dashboard")

    start_date, end_date = _current_period()
    employees = (
        User.objects.filter(profile__role="EMPLOYEE")
        .select_related("profile")
        .order_by("first_name", "username")
    )

    rows = []
    for employee in employees:
        metrics = calculate_performance(employee, start_date, end_date)
        metrics["calculated_category"] = metrics["category"]
        if employee.profile.manual_performance_category:
            metrics["category"] = employee.profile.manual_performance_category
        latest_review = employee.performance_reviews.first()
        rows.append({"employee": employee, "metrics": metrics, "latest_review": latest_review})

    categories = {
        "EXCELLENT": sum(row["metrics"]["category"] == "EXCELLENT" for row in rows),
        "GOOD": sum(row["metrics"]["category"] == "GOOD" for row in rows),
        "AVERAGE": sum(row["metrics"]["category"] == "AVERAGE" for row in rows),
        "POOR": sum(row["metrics"]["category"] == "POOR" for row in rows),
    }

    return render(
        request,
        "performance/list.html",
        {
            "rows": rows,
            "categories": categories,
            "start_date": start_date,
            "end_date": end_date,
        },
    )


@login_required
def performance_detail(request, user_id):
    if not _is_admin(request):
        return redirect("dashboard")

    employee = get_object_or_404(
        User.objects.select_related("profile"), id=user_id, profile__role="EMPLOYEE"
    )
    start_date, end_date = _current_period()
    metrics = calculate_performance(employee, start_date, end_date)
    metrics["calculated_category"] = metrics["category"]
    if employee.profile.manual_performance_category:
        metrics["category"] = employee.profile.manual_performance_category
    history = employee.performance_reviews.select_related("reviewed_by").all()[:8]

    if request.method == "POST":
        form = PerformanceReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.employee = employee
            review.reviewed_by = request.user
            metrics = calculate_performance(
                employee,
                form.cleaned_data["review_start"],
                form.cleaned_data["review_end"],
            )
            for key in (
                "review_start",
                "review_end",
                "task_completion",
                "on_time_delivery",
                "delayed_tasks",
                "approved_leaves",
                "unapproved_absences",
                "attendance_score",
                "leave_discipline",
                "overall_score",
                "category",
            ):
                if key in metrics:
                    setattr(review, key, metrics[key])
            selected_category = form.cleaned_data["category"]
            review.category = selected_category or metrics["category"]
            review.comment = form.cleaned_data.get("comment", "")
            review.save()
            employee.profile.manual_performance_category = selected_category
            employee.profile.save(update_fields=["manual_performance_category"])
            messages.success(request, f"Performance review saved for {employee.get_full_name() or employee.username}.")
            return redirect("performance:detail", user_id=employee.id)
    else:
        form = PerformanceReviewForm(
            initial={
                "review_start": start_date,
                "review_end": end_date,
                "category": employee.profile.manual_performance_category,
            }
        )

    return render(
        request,
        "performance/detail.html",
        {
            "employee": employee,
            "metrics": metrics,
            "history": history,
            "form": form,
        },
    )
