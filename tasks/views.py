from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from .forms import CommentForm, TaskForm
from .models import Task, TaskHistory

def role(request):
    return getattr(getattr(request.user, "profile", None), "role", "EMPLOYEE")


def _manager_scope(user):
    return Task.objects.filter(
        Q(created_by=user)
        | Q(assigned_to__profile__department=user.profile.department)
        | Q(project__team__department__name=user.profile.department)
    )


def _can_access_task(user, task):
    user_role = getattr(getattr(user, "profile", None), "role", "EMPLOYEE")
    if user_role == "ADMIN":
        return True
    if user_role == "MANAGER":
        return _manager_scope(user).filter(pk=task.pk).exists()
    return task.assigned_to_id == user.id


@login_required
def task_list(request):
    r = role(request)
    if r == "ADMIN":
        tasks = Task.objects.select_related("assigned_to", "created_by").all().order_by("-created_at")
    elif r == "MANAGER":
        tasks = _manager_scope(request.user).select_related("assigned_to", "created_by").order_by("-created_at")
    else:
        tasks = Task.objects.filter(assigned_to=request.user).select_related("assigned_to", "created_by").order_by("deadline")
    return render(request, "tasks/list.html", {"tasks": tasks})

@login_required
def task_create(request):
    if role(request) not in ("ADMIN", "MANAGER"):
        return redirect("task_list")
    if request.method == "POST":
        form = TaskForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            task.created_by = request.user
            task.save()
            TaskHistory.objects.create(task=task, user=request.user, action=f"Task created and assigned to {task.assigned_to.username}")
            messages.success(request, "Task created successfully.")
            return redirect("task_list")
    else:
        form = TaskForm(user=request.user)
    return render(request, "tasks/form.html", {"form": form, "title": "Create Task"})

@login_required
def task_detail(request, pk):
    task = get_object_or_404(Task.objects.select_related("assigned_to", "created_by"), pk=pk)
    if not _can_access_task(request.user, task):
        return redirect("task_list")
    form = CommentForm()
    return render(request, "tasks/detail.html", {"task": task, "form": form})

@login_required
def task_update(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not _can_access_task(request.user, task):
        return redirect("task_list")
    old_status = task.status
    if request.method == "POST":
        form = TaskForm(request.POST, request.FILES, instance=task, user=request.user)
        if form.is_valid():
            task = form.save(commit=False)
            if role(request) == "EMPLOYEE":
                task.assigned_to = request.user
            task.save()
            if old_status != task.status:
                TaskHistory.objects.create(task=task, user=request.user, action=f"Status changed from {old_status} to {task.status}")
            else:
                TaskHistory.objects.create(task=task, user=request.user, action="Task updated")
            messages.success(request, "Task updated.")
            return redirect("task_detail", pk=task.pk)
    else:
        form = TaskForm(instance=task, user=request.user)
    return render(request, "tasks/form.html", {"form": form, "title": "Update Task"})

@login_required
def add_comment(request, pk):
    task = get_object_or_404(Task, pk=pk)
    if not _can_access_task(request.user, task):
        return redirect("task_list")
    if request.method == "POST":
        form = CommentForm(request.POST)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.task = task
            comment.user = request.user
            comment.save()
            TaskHistory.objects.create(task=task, user=request.user, action="Added a comment")
    return redirect("task_detail", pk=pk)

@login_required
def kanban_update(request):
    if request.method != "POST":
        return JsonResponse({"ok": False}, status=405)
    task = get_object_or_404(Task, pk=request.POST.get("task_id"))
    if not _can_access_task(request.user, task):
        return JsonResponse({"ok": False}, status=403)
    new_status = request.POST.get("status")
    if new_status not in dict(Task.STATUSES):
        return JsonResponse({"ok": False}, status=400)
    task.status = new_status
    task.save(update_fields=["status", "updated_at"])
    TaskHistory.objects.create(task=task, user=request.user, action=f"Moved task to {new_status}")
    return JsonResponse({"ok": True})
