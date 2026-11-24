import csv
from io import BytesIO

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import render
from django.utils.dateparse import parse_date
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from tasks.models import Task
from organization.models import Project


def _can_view_reports(user):
    return getattr(getattr(user, "profile", None), "role", "") in ("ADMIN", "MANAGER")


def _safe_csv_cell(value):
    value = str(value)
    if value.startswith(("=", "+", "-", "@", "\t", "\r")):
        return "'" + value
    return value


def _report_tasks(request):
    tasks = Task.objects.select_related(
        "assigned_to", "project", "project__team", "project__team__department"
    )
    role = getattr(getattr(request.user, "profile", None), "role", "")
    if role == "MANAGER":
        tasks = tasks.filter(
            Q(project__team__department__name=request.user.profile.department)
            | Q(project__isnull=True, created_by=request.user)
        )

    start_value = request.GET.get("start_date", "")
    end_value = request.GET.get("end_date", "")
    start_date = parse_date(start_value) if start_value else None
    end_date = parse_date(end_value) if end_value else None
    if (start_value and not start_date) or (end_value and not end_date):
        raise ValueError("Enter valid report dates in YYYY-MM-DD format.")
    if start_date and end_date and start_date > end_date:
        raise ValueError("Report start date cannot be after its end date.")
    if start_date:
        tasks = tasks.filter(deadline__date__gte=start_date)
    if end_date:
        tasks = tasks.filter(deadline__date__lte=end_date)

    status = request.GET.get("status", "")
    if status:
        if status not in dict(Task.STATUSES):
            raise ValueError("Select a valid task status.")
        tasks = tasks.filter(status=status)

    project_id = request.GET.get("project", "")
    if project_id:
        try:
            project_id = int(project_id)
        except ValueError as exc:
            raise ValueError("Select a valid project.") from exc
        accessible_projects = Project.objects.all()
        if role == "MANAGER":
            accessible_projects = accessible_projects.filter(
                team__department__name=request.user.profile.department
            )
        if not accessible_projects.filter(pk=project_id).exists():
            raise ValueError("Select a project in your authorized scope.")
        tasks = tasks.filter(project_id=project_id)

    query = request.GET.get("q", "").strip()
    if query:
        tasks = tasks.filter(title__icontains=query)
    return tasks, {
        "start_date": start_value,
        "end_date": end_value,
        "status": status,
        "project": str(project_id) if project_id else "",
        "query": query,
        "projects": Project.objects.filter(status="ACTIVE")
        .filter(
            Q(team__department__name=request.user.profile.department)
            if role == "MANAGER"
            else Q()
        )
        .order_by("name"),
    }


@login_required
def reports_home(request):
    if not _can_view_reports(request.user):
        return HttpResponseRedirect("/dashboard/")
    try:
        tasks, filters = _report_tasks(request)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    stats = {
        "total": tasks.count(),
        "completed": tasks.filter(status="COMPLETED").count(),
        "pending": tasks.exclude(status="COMPLETED").count(),
        "overdue": sum(1 for t in tasks if t.is_overdue),
    }
    employees = tasks.values("assigned_to__username").annotate(total=Count("id")).order_by("-total")
    return render(
        request,
        "reports/home.html",
        {"stats": stats, "employees": employees, "filters": filters},
    )


@login_required
def task_csv(request):
    if not _can_view_reports(request.user):
        return HttpResponseRedirect("/dashboard/")
    try:
        tasks, _ = _report_tasks(request)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="task_report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Title", "Assigned To", "Priority", "Status", "Deadline", "Created"])
    for task in tasks:
        writer.writerow([
            _safe_csv_cell(task.title),
            _safe_csv_cell(task.assigned_to.username),
            _safe_csv_cell(task.get_priority_display()),
            _safe_csv_cell(task.get_status_display()),
            _safe_csv_cell(task.deadline.strftime("%Y-%m-%d %H:%M") if task.deadline else ""),
            _safe_csv_cell(task.created_at.strftime("%Y-%m-%d %H:%M")),
        ])
    return response


@login_required
def task_pdf(request):
    if not _can_view_reports(request.user):
        return HttpResponseRedirect("/dashboard/")
    try:
        tasks, _ = _report_tasks(request)
    except ValueError as exc:
        return HttpResponseBadRequest(str(exc))
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, title="Task Report")
    styles = getSampleStyleSheet()
    story = [Paragraph("Task report", styles["Title"]), Spacer(1, 20)]

    rows = [["Title", "Assigned To", "Priority", "Status", "Deadline", "Created"]]
    for task in tasks:
        rows.append([
            task.title,
            task.assigned_to.username,
            task.get_priority_display(),
            task.get_status_display(),
            task.deadline.strftime("%Y-%m-%d %H:%M") if task.deadline else "",
            task.created_at.strftime("%Y-%m-%d %H:%M"),
        ])

    table = Table(rows)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F6FED")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 1, colors.grey),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
    ]))
    story.append(table)

    doc.build(story)

    pdf = buffer.getvalue()
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="task_report.pdf"'
    return response
