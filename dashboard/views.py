from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db.models import Count
from django.shortcuts import redirect, render
from tasks.models import Task
from notifications.models import Notification
from scrum.models import Sprint
from performance.services import calculate_performance

@login_required
def dashboard(request):
    profile = getattr(request.user, "profile", None)
    if not profile:
        from accounts.models import Profile
        profile, _ = Profile.objects.get_or_create(user=request.user)
    if profile.role == "EMPLOYEE":
        tasks = Task.objects.filter(assigned_to=request.user)
        context = {
            "role": profile.role,
            "my_tasks": tasks,
            "total_tasks": tasks.count(),
            "pending": tasks.exclude(status="COMPLETED").count(),
            "completed": tasks.filter(status="COMPLETED").count(),
            "overdue": sum(1 for t in tasks if t.is_overdue),
            "notifications": Notification.objects.filter(user=request.user, is_read=False)[:5],
        }
        return render(request, "dashboard/employee.html", context)

    tasks = Task.objects.all()
    performance_counts = {"EXCELLENT": 0, "GOOD": 0, "AVERAGE": 0, "POOR": 0}
    if profile.role == "ADMIN":
        for employee in User.objects.filter(profile__role="EMPLOYEE").select_related("profile"):
            category = employee.profile.manual_performance_category
            if not category:
                category = calculate_performance(employee)["category"]
            performance_counts[category] += 1
    context = {
        "role": profile.role,
        "employees": User.objects.filter(profile__role="EMPLOYEE").count(),
        "total_tasks": tasks.count(),
        "pending": tasks.exclude(status="COMPLETED").count(),
        "completed": tasks.filter(status="COMPLETED").count(),
        "overdue": sum(1 for t in tasks if t.is_overdue),
        "sprints": Sprint.objects.filter(closed=False).count(),
        "team_stats": tasks.values("assigned_to__username").annotate(total=Count("id")).order_by("-total")[:8],
        "performance_counts": performance_counts,
    }
    return render(request, "dashboard/manager.html", context)
