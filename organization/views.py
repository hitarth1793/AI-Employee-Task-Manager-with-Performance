from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import DepartmentForm, ProjectForm, TeamForm
from .models import Department, Project, Team


def _role(user):
    return getattr(getattr(user, "profile", None), "role", "")


@login_required
def department_list(request):
    if _role(request.user) not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")
    return render(
        request,
        "organization/departments.html",
        {"departments": Department.objects.all(), "can_manage": _role(request.user) == "ADMIN"},
    )


@login_required
def department_create(request):
    if _role(request.user) != "ADMIN":
        return redirect("dashboard")
    form = DepartmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department created.")
        return redirect("organization:departments")
    return render(request, "organization/department_form.html", {"form": form, "title": "Create Department"})


@login_required
def department_edit(request, pk):
    if _role(request.user) != "ADMIN":
        return redirect("dashboard")
    department = get_object_or_404(Department, pk=pk)
    form = DepartmentForm(request.POST or None, instance=department)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Department updated.")
        return redirect("organization:departments")
    return render(request, "organization/department_form.html", {"form": form, "title": "Edit Department"})


@login_required
def department_delete(request, pk):
    if _role(request.user) != "ADMIN":
        return redirect("dashboard")
    department = get_object_or_404(Department, pk=pk)
    if request.method != "POST":
        return redirect("organization:departments")
    try:
        department.delete()
    except ProtectedError:
        messages.error(request, "Reassign or remove the department's teams before deleting it.")
    else:
        messages.success(request, "Department deleted.")
    return redirect("organization:departments")


@login_required
def team_list(request):
    if _role(request.user) not in ("ADMIN", "MANAGER", "EMPLOYEE"):
        return redirect("dashboard")
    teams = Team.objects.select_related("department").prefetch_related("members")
    role = _role(request.user)
    if role == "MANAGER":
        teams = teams.filter(department__name=request.user.profile.department)
    elif role == "EMPLOYEE":
        teams = teams.filter(members=request.user)
    return render(request, "organization/teams.html", {"teams": teams, "can_manage": role in ("ADMIN", "MANAGER")})


@login_required
def team_detail(request, pk):
    team = get_object_or_404(
        Team.objects.select_related("department").prefetch_related("members"),
        pk=pk,
    )
    role = _role(request.user)
    if role == "MANAGER" and team.department.name != request.user.profile.department:
        return redirect("organization:teams")
    if role == "EMPLOYEE" and not team.members.filter(pk=request.user.pk).exists():
        return redirect("organization:teams")
    if role not in ("ADMIN", "MANAGER", "EMPLOYEE"):
        return redirect("dashboard")
    return render(request, "organization/team_detail.html", {"team": team, "can_manage": role in ("ADMIN", "MANAGER")})


def _save_team_membership(team, previous_members, current_members):
    removed = previous_members - current_members
    for user in removed:
        profile = user.profile
        if profile.team == team.name:
            profile.team = ""
            profile.save(update_fields=["team"])
    for user in current_members:
        profile = user.profile
        profile.team = team.name
        profile.department = team.department.name
        profile.save(update_fields=["team", "department"])


@login_required
def team_create(request):
    if _role(request.user) not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")
    form = TeamForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        team = form.save()
        _save_team_membership(team, set(), set(team.members.all()))
        messages.success(request, "Team created.")
        return redirect("organization:team_detail", pk=team.pk)
    return render(request, "organization/team_form.html", {"form": form, "title": "Create Team"})


@login_required
def team_edit(request, pk):
    if _role(request.user) not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")
    team = get_object_or_404(Team.objects.select_related("department"), pk=pk)
    if _role(request.user) == "MANAGER" and team.department.name != request.user.profile.department:
        return redirect("organization:teams")
    previous = set(team.members.all())
    form = TeamForm(request.POST or None, instance=team, user=request.user)
    if request.method == "POST" and form.is_valid():
        team = form.save()
        _save_team_membership(team, previous, set(team.members.all()))
        messages.success(request, "Team updated.")
        return redirect("organization:team_detail", pk=team.pk)
    return render(request, "organization/team_form.html", {"form": form, "title": "Edit Team"})


@login_required
def project_list(request):
    role = _role(request.user)
    if role not in ("ADMIN", "MANAGER", "EMPLOYEE"):
        return redirect("dashboard")
    projects = Project.objects.select_related("team", "team__department")
    if role == "MANAGER":
        projects = projects.filter(team__department__name=request.user.profile.department)
    elif role == "EMPLOYEE":
        projects = projects.filter(team__members=request.user)
    status = request.GET.get("status", "ACTIVE")
    if status in dict(Project.STATUS_CHOICES):
        projects = projects.filter(status=status)
    query = request.GET.get("q", "").strip()
    if query:
        projects = projects.filter(name__icontains=query)
    return render(
        request,
        "organization/projects.html",
        {"projects": projects.distinct(), "can_manage": role in ("ADMIN", "MANAGER"), "status": status, "query": query},
    )


@login_required
def project_create(request):
    if _role(request.user) not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")
    form = ProjectForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        project = form.save(commit=False)
        project.created_by = request.user
        project.save()
        messages.success(request, "Project created.")
        return redirect("organization:projects")
    return render(request, "organization/project_form.html", {"form": form, "title": "Create Project"})


@login_required
def project_edit(request, pk):
    role = _role(request.user)
    if role not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")
    project = get_object_or_404(Project.objects.select_related("team__department"), pk=pk)
    if role == "MANAGER" and project.team.department.name != request.user.profile.department:
        return redirect("organization:projects")
    form = ProjectForm(request.POST or None, instance=project, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Project updated.")
        return redirect("organization:projects")
    return render(request, "organization/project_form.html", {"form": form, "title": "Edit Project"})


@login_required
def project_archive(request, pk):
    role = _role(request.user)
    if role not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")
    project = get_object_or_404(Project.objects.select_related("team__department"), pk=pk)
    if role == "MANAGER" and project.team.department.name != request.user.profile.department:
        return redirect("organization:projects")
    if request.method == "POST":
        project.status = "ARCHIVED"
        project.save(update_fields=["status", "updated_at"])
        messages.success(request, "Project archived.")
    return redirect("organization:projects")
