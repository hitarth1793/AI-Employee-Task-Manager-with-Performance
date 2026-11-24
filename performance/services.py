from datetime import timedelta
from decimal import Decimal

from django.db.models import Q
from django.utils import timezone

from leave_attendance.models import Attendance, LeaveRequest
from tasks.models import Task


def category_from_score(score):
    if score >= 90:
        return "EXCELLENT"
    if score >= 75:
        return "GOOD"
    if score >= 50:
        return "AVERAGE"
    return "POOR"


def _approved_leave_dates(employee, start_date, end_date):
    covered = set()
    requests = LeaveRequest.objects.filter(
        user=employee,
        status="APPROVED",
        start_date__lte=end_date,
        end_date__gte=start_date,
    )
    for leave in requests:
        current = max(leave.start_date, start_date)
        last = min(leave.end_date, end_date)
        while current <= last:
            covered.add(current)
            current += timedelta(days=1)
    return covered, requests.count()


def calculate_performance(employee, start_date=None, end_date=None):
    today = timezone.localdate()
    end_date = end_date or today
    start_date = start_date or end_date.replace(day=1)

    if start_date > end_date:
        raise ValueError("Review start date cannot be after the end date.")

    # Tasks active during the review period. This includes older tasks that were
    # updated during the period as well as tasks created/deadlined in the period.
    tasks = Task.objects.filter(assigned_to=employee).filter(
        Q(created_at__date__range=(start_date, end_date))
        | Q(updated_at__date__range=(start_date, end_date))
        | Q(deadline__date__range=(start_date, end_date))
        | (
            Q(created_at__date__lt=start_date)
            & (Q(deadline__isnull=True) | Q(deadline__date__gte=start_date))
        )
    ).distinct()

    total_tasks = tasks.count()
    completed_tasks = list(tasks.filter(status="COMPLETED"))
    completed_count = len(completed_tasks)
    task_completion = (completed_count / total_tasks * 100) if total_tasks else 100.0

    completed_with_deadline = [task for task in completed_tasks if task.deadline]
    on_time_count = sum(1 for task in completed_with_deadline if task.updated_at <= task.deadline)
    on_time_delivery = (
        on_time_count / len(completed_with_deadline) * 100
        if completed_with_deadline
        else 100.0
    )

    delayed_incomplete = sum(1 for task in tasks if task.is_overdue)
    delayed_completed = sum(
        1 for task in completed_with_deadline if task.updated_at > task.deadline
    )
    delayed_tasks = delayed_incomplete + delayed_completed

    attendance = Attendance.objects.filter(
        user=employee, date__range=(start_date, end_date)
    )
    approved_leave_dates, approved_leave_count = _approved_leave_dates(
        employee, start_date, end_date
    )
    present_count = attendance.filter(status__in=("PRESENT", "WFH")).count()
    absent_records = attendance.filter(status="ABSENT")
    absent_count = sum(
        1 for record in absent_records if record.date not in approved_leave_dates
    )
    attendance_total = present_count + absent_count
    attendance_score = present_count / attendance_total * 100 if attendance_total else 100.0

    unapproved_absences = 0
    for record in absent_records:
        if record.date not in approved_leave_dates:
            unapproved_absences += 1

    # Approved leave is not penalized. Leave discipline is affected only by
    # recorded absences that are not covered by an approved leave request.
    leave_discipline = max(0.0, 100.0 - (unapproved_absences * 20.0))

    overall_score = (
        task_completion * 0.35
        + on_time_delivery * 0.30
        + attendance_score * 0.25
        + leave_discipline * 0.10
    )
    overall_score = round(overall_score, 2)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_tasks": total_tasks,
        "completed_tasks": completed_count,
        "task_completion": round(task_completion, 2),
        "on_time_delivery": round(on_time_delivery, 2),
        "delayed_tasks": delayed_tasks,
        "attendance_score": round(attendance_score, 2),
        "attendance_records": attendance_total,
        "present_records": present_count,
        "absent_records": absent_count,
        "approved_leaves": approved_leave_count,
        "unapproved_absences": unapproved_absences,
        "leave_discipline": round(leave_discipline, 2),
        "overall_score": Decimal(str(overall_score)),
        "category": category_from_score(overall_score),
    }
