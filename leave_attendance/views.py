from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseNotAllowed
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import AttendanceForm, LeaveForm
from .models import Attendance, LeaveBalance, LeaveRequest

@login_required
def leave_home(request):
    balance, _ = LeaveBalance.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = LeaveForm(request.POST)
        if form.is_valid():
            leave = form.save(commit=False)
            leave.user = request.user
            leave.save()
            messages.success(request, "Leave request submitted.")
            return redirect("leave")
    else:
        form = LeaveForm()
    leaves = LeaveRequest.objects.filter(user=request.user).order_by("-created_at")
    return render(request, "leave/home.html", {"balance": balance, "form": form, "leaves": leaves})

@login_required
def attendance_home(request):
    role = getattr(request.user.profile, "role", "")
    if role in ("ADMIN", "MANAGER"):
        records = Attendance.objects.select_related("user")
        if role == "MANAGER":
            records = records.filter(user__profile__department=request.user.profile.department)
        records = records.order_by("-date")
    else:
        records = Attendance.objects.filter(user=request.user).order_by("-date")
    form = AttendanceForm(user=request.user)
    if request.method == "POST" and role == "EMPLOYEE":
        action = request.POST.get("action")
        if action not in ("check_in", "check_out"):
            return HttpResponseNotAllowed(["GET", "POST"])
        now = timezone.localtime()
        record, _ = Attendance.objects.get_or_create(
            user=request.user,
            date=timezone.localdate(now),
            defaults={"status": "PRESENT"},
        )
        if action == "check_in":
            if record.check_in:
                messages.error(request, "You have already checked in today.")
            else:
                record.check_in = now.time().replace(microsecond=0)
                record.save(update_fields=["check_in"])
                messages.success(request, "Check-in recorded.")
        elif not record.check_in:
            messages.error(request, "Check in before recording a check-out.")
        elif record.check_out:
            messages.error(request, "You have already checked out today.")
        else:
            record.check_out = now.time().replace(microsecond=0)
            record.save(update_fields=["check_out"])
            messages.success(request, "Check-out recorded.")
        return redirect("attendance")
    if request.method == "POST" and role in ("ADMIN", "MANAGER"):
        form = AttendanceForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("attendance")
    return render(request, "leave/attendance.html", {"records": records, "form": form})

@login_required
def leave_approvals(request):
    role = getattr(request.user.profile, "role", "")
    if role not in ("ADMIN", "MANAGER"):
        return redirect("leave")
    leaves = LeaveRequest.objects.select_related("user").filter(status="PENDING")
    if role == "MANAGER":
        leaves = leaves.filter(user__profile__department=request.user.profile.department)
    leaves = leaves.order_by("-created_at")
    return render(request, "leave/approvals.html", {"leaves": leaves})

@login_required
def leave_decide(request, pk, decision):
    role = getattr(request.user.profile, "role", "")
    if role not in ("ADMIN", "MANAGER"):
        return redirect("leave")
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    leave = get_object_or_404(LeaveRequest, pk=pk)
    if role == "MANAGER" and leave.user.profile.department != request.user.profile.department:
        return HttpResponseForbidden()
    if decision in ("approve", "reject"):
        leave.status = "APPROVED" if decision == "approve" else "REJECTED"
        leave.reviewed_by = request.user
        leave.save()
    return redirect("leave_approvals")
