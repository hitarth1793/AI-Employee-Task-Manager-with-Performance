from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.shortcuts import get_object_or_404, redirect, render
from .forms import ProfileForm, RegisterForm
from .models import Profile


def ensure_profile(user):
    profile, _ = Profile.objects.get_or_create(user=user, defaults={"role": "EMPLOYEE"})
    return profile


class RoleLoginView(LoginView):
    template_name = "accounts/login.html"


def register_view(request):
    if request.method == "POST":
        form = RegisterForm(request.POST, allowed_roles=[("EMPLOYEE", "Employee")])
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully.")
            return redirect("dashboard")
    else:
        form = RegisterForm(allowed_roles=[("EMPLOYEE", "Employee")])
    return render(request, "accounts/register.html", {"form": form})


@login_required
def profile_view(request):
    profile = ensure_profile(request.user)
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Profile updated.")
            return redirect("accounts:profile")
    else:
        form = ProfileForm(instance=profile)
    return render(request, "accounts/profile.html", {"form": form, "profile": profile})


@login_required
def employee_list(request):
    profile = ensure_profile(request.user)
    if profile.role not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")
    employees = Profile.objects.select_related("user").filter(role="EMPLOYEE").order_by("user__first_name")
    return render(request, "accounts/employees.html", {"employees": employees})


@login_required
def employee_create(request):
    profile = ensure_profile(request.user)
    if profile.role not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")

    allowed_roles = [("MANAGER", "Manager"), ("EMPLOYEE", "Employee")] if profile.role == "ADMIN" else [("EMPLOYEE", "Employee")]

    if request.method == "POST":
        form = RegisterForm(request.POST, allowed_roles=allowed_roles)
        if form.is_valid():
            form.save()
            messages.success(request, "User created successfully.")
            return redirect("accounts:employees")
    else:
        form = RegisterForm(allowed_roles=allowed_roles)

    return render(request, "accounts/add_user.html", {"form": form, "allowed_roles": allowed_roles})


@login_required
def employee_edit(request, user_id):
    profile = ensure_profile(request.user)
    if profile.role not in ("ADMIN", "MANAGER"):
        return redirect("dashboard")
    employee = get_object_or_404(Profile, user_id=user_id, role="EMPLOYEE")
    if request.method == "POST":
        form = ProfileForm(request.POST, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "Employee details updated.")
            return redirect("accounts:employees")
    else:
        form = ProfileForm(instance=employee)
    return render(request, "accounts/employee_edit.html", {"form": form, "employee": employee})
