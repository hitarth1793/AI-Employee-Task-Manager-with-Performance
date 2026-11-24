import csv
from datetime import date, datetime, time
from io import StringIO

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from accounts.models import Profile
from organization.models import Department, Project, Team
from tasks.models import Task


class ReportAccessTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="qa_manager", password="SecurePass!234")
        Profile.objects.create(user=self.manager, role="MANAGER", department="Engineering")
        self.employee = User.objects.create_user(username="qa_employee", password="SecurePass!234")
        Profile.objects.create(user=self.employee, role="EMPLOYEE", department="Engineering")
        Task.objects.create(
            title="Report scope test task",
            assigned_to=self.employee,
            created_by=self.manager,
        )

    def test_employee_cannot_view_manager_reports_or_exports(self):
        self.client.force_login(self.employee)
        for url in ("/reports/", "/reports/tasks.csv", "/reports/tasks.pdf"):
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertEqual(response.url, "/dashboard/")

    def test_manager_can_view_and_export_task_reports(self):
        self.client.force_login(self.manager)
        page = self.client.get("/reports/")
        csv = self.client.get("/reports/tasks.csv")
        pdf = self.client.get("/reports/tasks.pdf")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(csv.status_code, 200)
        self.assertIn("text/csv", csv["Content-Type"])
        self.assertIn(b"Report scope test task", csv.content)
        self.assertEqual(pdf.status_code, 200)
        self.assertIn("application/pdf", pdf["Content-Type"])

    def test_csv_export_neutralizes_spreadsheet_formula_cells(self):
        Task.objects.create(
            title='=HYPERLINK("https://example.test","open")',
            assigned_to=self.employee,
            created_by=self.manager,
        )
        self.client.force_login(self.manager)
        response = self.client.get("/reports/tasks.csv")
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        self.assertEqual(rows[-1][0], "'=HYPERLINK(\"https://example.test\",\"open\")")

    def test_report_and_csv_export_apply_date_project_and_status_filters(self):
        department = Department.objects.create(name="Engineering")
        team = Team.objects.create(name="Reporting", department=department)
        team.members.add(self.employee)
        project = Project.objects.create(
            name="Filtered report project",
            team=team,
            start_date=date(2026, 10, 1),
            end_date=date(2026, 12, 31),
            created_by=self.manager,
        )
        included = Task.objects.create(
            title="Included completed task",
            assigned_to=self.employee,
            created_by=self.manager,
            project=project,
            status="COMPLETED",
            deadline=timezone.make_aware(datetime.combine(date(2026, 10, 10), time(12))),
        )
        excluded = Task.objects.create(
            title="Excluded open task",
            assigned_to=self.employee,
            created_by=self.manager,
            project=project,
            status="TODO",
            deadline=timezone.make_aware(datetime.combine(date(2026, 11, 10), time(12))),
        )
        self.client.force_login(self.manager)
        query = {
            "project": project.pk,
            "status": "COMPLETED",
            "start_date": "2026-10-05",
            "end_date": "2026-10-31",
        }
        page = self.client.get("/reports/", query)
        response = self.client.get("/reports/tasks.csv", query)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.context["stats"]["total"], 1)
        self.assertEqual(page.context["stats"]["completed"], 1)
        self.assertEqual(response.status_code, 200)
        rows = list(csv.reader(StringIO(response.content.decode("utf-8"))))
        exported_titles = [row[0] for row in rows[1:]]
        self.assertIn(included.title, exported_titles)
        self.assertNotIn(excluded.title, exported_titles)

    def test_report_rejects_invalid_or_reversed_dates(self):
        self.client.force_login(self.manager)
        self.assertEqual(
            self.client.get("/reports/", {"start_date": "not-a-date"}).status_code,
            400,
        )
        self.assertEqual(
            self.client.get(
                "/reports/", {"start_date": "2026-11-01", "end_date": "2026-10-01"}
            ).status_code,
            400,
        )
