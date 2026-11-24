from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from .forms import SprintForm
from .models import Sprint

@login_required
def board(request):
    from tasks.models import Task
    role = getattr(request.user.profile, "role", "EMPLOYEE")
    if role == "EMPLOYEE":
        tasks = Task.objects.filter(assigned_to=request.user)
    elif role == "MANAGER":
        tasks = Task.objects.filter(
            Q(created_by=request.user)
            | Q(assigned_to__profile__department=request.user.profile.department)
        )
    else:
        tasks = Task.objects.all()
    columns = [(code, label, tasks.filter(status=code)) for code, label in Task.STATUSES]
    return render(request, "scrum/board.html", {"columns": columns})

@login_required
def sprint_list(request):
    role = getattr(request.user.profile, "role", "EMPLOYEE")
    sprints = Sprint.objects.all()
    if role == "EMPLOYEE":
        sprints = sprints.filter(tasks__assigned_to=request.user)
    elif role == "MANAGER":
        sprints = sprints.filter(
            Q(created_by=request.user)
            | Q(tasks__assigned_to__profile__department=request.user.profile.department)
        )
    sprints = sprints.prefetch_related("tasks").distinct().order_by("-start_date")
    return render(request, "scrum/sprints.html", {"sprints": sprints})

@login_required
def sprint_create(request):
    if getattr(request.user.profile, "role", "") not in ("ADMIN", "MANAGER"):
        return redirect("sprint_list")
    if request.method == "POST":
        form = SprintForm(request.POST, user=request.user)
        if form.is_valid():
            sprint = form.save(commit=False)
            sprint.created_by = request.user
            sprint.save()
            form.save_m2m()
            messages.success(request, "Sprint created.")
            return redirect("sprint_list")
    else:
        form = SprintForm(user=request.user)
    return render(request, "scrum/sprint_form.html", {"form": form})
