from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Profile
from leave_attendance.models import Attendance, LeaveRequest
from scrum.models import Sprint


class FullCoverageRegressionTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username="coverage_admin",
            email="admin@example.test",
            password="admin123!",
        )
        Profile.objects.create(user=self.admin, role="ADMIN")
        self.manager = User.objects.create_user(
            username="coverage_manager",
            email="manager@example.test",
            password="manager123!",
        )
        Profile.objects.create(
            user=self.manager, role="MANAGER", department="Engineering"
        )
        self.employee = User.objects.create_user(
            username="coverage_employee",
            email="employee@example.test",
            password="employee123!",
        )
        Profile.objects.create(
            user=self.employee, role="EMPLOYEE", department="Engineering"
        )

    def test_tc003_admin_valid_login(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.admin.username, "password": "admin123!"},
        )
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_tc005_unknown_username_is_rejected(self):
        response = self.client.post(
            reverse("accounts:login"),
            {"username": "not-a-user", "password": "AnyPass123!"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_tc006_blank_login_fields_are_rejected(self):
        response = self.client.post(
            reverse("accounts:login"), {"username": "", "password": ""}
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_tc009_valid_public_registration_creates_employee_account(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": "new_coverage_user",
                "first_name": "New",
                "last_name": "Employee",
                "email": "newuser@example.test",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "role": "EMPLOYEE",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="new_coverage_user")
        self.assertEqual(user.profile.role, "EMPLOYEE")
        self.assertTrue(user.check_password("Password123!"))

    def test_tc010_duplicate_username_registration_is_rejected(self):
        response = self.client.post(
            reverse("accounts:register"),
            {
                "username": self.employee.username,
                "first_name": "Duplicate",
                "last_name": "User",
                "email": "another@example.test",
                "password": "Password123!",
                "confirm_password": "Password123!",
                "role": "EMPLOYEE",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(username=self.employee.username).count(), 1)

    def test_tc041_employee_leave_submission_and_manager_approval(self):
        self.client.force_login(self.employee)
        start = timezone.localdate() + timedelta(days=1)
        response = self.client.post(
            reverse("leave"),
            {
                "leave_type": "CASUAL",
                "start_date": start.isoformat(),
                "end_date": (start + timedelta(days=2)).isoformat(),
                "reason": "Coverage QA leave request",
            },
        )
        self.assertRedirects(response, reverse("leave"))
        leave = LeaveRequest.objects.get(user=self.employee)
        self.assertEqual(leave.status, "PENDING")

        self.client.force_login(self.manager)
        response = self.client.post(
            reverse("leave_decide", args=(leave.pk, "approve"))
        )
        self.assertRedirects(response, reverse("leave_approvals"))
        leave.refresh_from_db()
        self.assertEqual(leave.status, "APPROVED")

    def test_tc048_employee_attendance_check_in_and_check_out(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            reverse("attendance"), {"action": "check_in"}
        )
        self.assertRedirects(response, reverse("attendance"))
        record = Attendance.objects.get(
            user=self.employee, date=timezone.localdate()
        )
        self.assertIsNotNone(record.check_in)
        first_check_in = record.check_in

        self.client.post(reverse("attendance"), {"action": "check_in"})
        record.refresh_from_db()
        self.assertEqual(record.check_in, first_check_in)
        self.assertIsNone(record.check_out)

        response = self.client.post(
            reverse("attendance"), {"action": "check_out"}
        )
        self.assertRedirects(response, reverse("attendance"))
        record.refresh_from_db()
        self.assertIsNotNone(record.check_out)
        self.assertGreaterEqual(record.check_out, record.check_in)

    def test_tc066_manager_can_create_sprint(self):
        self.client.force_login(self.manager)
        start = timezone.localdate()
        response = self.client.post(
            reverse("sprint_create"),
            {
                "name": "Coverage Sprint",
                "start_date": start.isoformat(),
                "end_date": (start + timedelta(days=14)).isoformat(),
                "goal": "Validate sprint creation",
                "tasks": [],
            },
        )
        self.assertRedirects(response, reverse("sprint_list"))
        sprint = Sprint.objects.get(name="Coverage Sprint")
        self.assertEqual(sprint.created_by, self.manager)
        self.assertEqual(sprint.start_date, start)

    @override_settings(GEMINI_API_KEY="", AI_API_URL="", AI_API_KEY="")
    def test_tc138_assistant_answers_employee_task_lookup(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            reverse("assistant_ask"),
            {"question": "What are my pending tasks?"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["answer"], "You currently have no pending tasks."
        )
