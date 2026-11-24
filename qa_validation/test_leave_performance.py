from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Profile
from leave_attendance.models import Attendance, LeaveRequest
from performance.services import calculate_performance, category_from_score
from tasks.models import Task


class LeaveAndPerformanceFlowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="qa_admin", password="SecurePass!234")
        Profile.objects.create(user=self.admin, role="ADMIN")
        self.manager = User.objects.create_user(username="qa_manager", password="SecurePass!234")
        Profile.objects.create(user=self.manager, role="MANAGER")
        self.employee = User.objects.create_user(username="qa_employee", password="SecurePass!234")
        Profile.objects.create(user=self.employee, role="EMPLOYEE")

    def test_employee_submits_leave_and_manager_approves_with_post(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/leave/",
            {
                "leave_type": "CASUAL",
                "start_date": "2026-11-02",
                "end_date": "2026-11-03",
                "reason": "QA test",
            },
        )
        self.assertEqual(response.status_code, 302)
        leave = LeaveRequest.objects.get(user=self.employee)
        self.assertEqual(leave.status, "PENDING")

        self.client.force_login(self.manager)
        response = self.client.get(f"/leave/approvals/{leave.pk}/approve/")
        leave.refresh_from_db()
        self.assertNotEqual(leave.status, "APPROVED")
        self.assertIn(response.status_code, (302, 405))

        response = self.client.post(f"/leave/approvals/{leave.pk}/approve/")
        leave.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(leave.status, "APPROVED")

    def test_leave_request_rejects_end_date_before_start_date(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/leave/",
            {
                "leave_type": "CASUAL",
                "start_date": "2026-11-04",
                "end_date": "2026-11-02",
                "reason": "Invalid date range",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LeaveRequest.objects.filter(user=self.employee).exists())

    def test_approved_leave_is_not_counted_as_absence_in_performance(self):
        start, end = date(2026, 11, 1), date(2026, 11, 5)
        LeaveRequest.objects.create(
            user=self.employee,
            leave_type="CASUAL",
            start_date=date(2026, 11, 3),
            end_date=date(2026, 11, 3),
            status="APPROVED",
            reviewed_by=self.manager,
        )
        for day in (1, 2, 4, 5):
            Attendance.objects.create(
                user=self.employee, date=date(2026, 11, day), status="PRESENT"
            )
        baseline = calculate_performance(self.employee, start, end)
        Attendance.objects.create(
            user=self.employee, date=date(2026, 11, 3), status="ABSENT"
        )
        with_approved_leave = calculate_performance(self.employee, start, end)
        self.assertEqual(baseline["attendance_score"], with_approved_leave["attendance_score"])
        self.assertEqual(baseline["leave_discipline"], with_approved_leave["leave_discipline"])
        self.assertEqual(baseline["overall_score"], with_approved_leave["overall_score"])

    def test_unapproved_absence_affects_leave_discipline(self):
        start, end = date(2026, 11, 1), date(2026, 11, 5)
        baseline = calculate_performance(self.employee, start, end)
        Attendance.objects.create(
            user=self.employee, date=date(2026, 11, 3), status="ABSENT"
        )
        after_absence = calculate_performance(self.employee, start, end)
        self.assertLess(after_absence["leave_discipline"], baseline["leave_discipline"])
        self.assertEqual(after_absence["unapproved_absences"], 1)

    def test_performance_categories_cover_all_required_thresholds(self):
        self.assertEqual(category_from_score(90), "EXCELLENT")
        self.assertEqual(category_from_score(89.99), "GOOD")
        self.assertEqual(category_from_score(75), "GOOD")
        self.assertEqual(category_from_score(74.99), "AVERAGE")
        self.assertEqual(category_from_score(50), "AVERAGE")
        self.assertEqual(category_from_score(49.99), "POOR")

    def test_employee_cannot_view_admin_performance_review(self):
        self.client.force_login(self.employee)
        response = self.client.get(f"/performance/employee/{self.employee.pk}/")
        self.assertEqual(response.status_code, 302)

    def test_admin_can_set_and_change_employee_performance_rating(self):
        self.client.force_login(self.admin)
        review_url = f"/performance/employee/{self.employee.pk}/"
        form_data = {
            "review_start": "2026-10-01",
            "review_end": "2026-10-06",
            "category": "POOR",
            "comment": "Needs improvement",
        }

        response = self.client.post(review_url, form_data)
        self.assertEqual(response.status_code, 302)
        self.employee.profile.refresh_from_db()
        self.assertEqual(self.employee.profile.manual_performance_category, "POOR")
        self.assertEqual(self.employee.performance_reviews.latest("created_at").category, "POOR")
        dashboard_response = self.client.get("/dashboard/")
        self.assertEqual(dashboard_response.context["performance_counts"]["POOR"], 1)
        list_response = self.client.get("/performance/")
        self.assertEqual(list_response.context["rows"][0]["metrics"]["category"], "POOR")

        form_data["category"] = "GOOD"
        response = self.client.post(review_url, form_data)
        self.assertEqual(response.status_code, 302)
        self.employee.profile.refresh_from_db()
        self.assertEqual(self.employee.profile.manual_performance_category, "GOOD")
        self.assertEqual(self.employee.performance_reviews.latest("created_at").category, "GOOD")

    def test_admin_can_restore_calculated_employee_rating(self):
        self.employee.profile.manual_performance_category = "POOR"
        self.employee.profile.save(update_fields=["manual_performance_category"])
        self.client.force_login(self.admin)

        response = self.client.post(
            f"/performance/employee/{self.employee.pk}/",
            {
                "review_start": "2026-10-01",
                "review_end": "2026-10-06",
                "category": "",
                "comment": "",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.employee.profile.refresh_from_db()
        self.assertEqual(self.employee.profile.manual_performance_category, "")
        self.assertEqual(
            self.employee.performance_reviews.latest("created_at").category,
            calculate_performance(self.employee, date(2026, 10, 1), date(2026, 10, 6))["category"],
        )

    def test_task_completion_and_deadline_contribute_to_review(self):
        start, end = date(2026, 11, 1), date(2026, 11, 30)
        first = Task.objects.create(
            title="Complete on time",
            assigned_to=self.employee,
            created_by=self.manager,
            status="COMPLETED",
        )
        before = calculate_performance(self.employee, start, end)
        Task.objects.create(
            title="Still open",
            assigned_to=self.employee,
            created_by=self.manager,
            status="TODO",
        )
        after = calculate_performance(self.employee, start, end)
        self.assertLess(after["task_completion"], before["task_completion"])
        self.assertEqual(first.status, "COMPLETED")
