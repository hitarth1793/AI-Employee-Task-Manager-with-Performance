from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Profile


class AuthenticationFlowTests(TestCase):
    def setUp(self):
        self.employee = User.objects.create_user(
            username="qa_employee",
            password="SecurePass!234",
            first_name="Quinn",
            email="quinn@example.test",
        )
        Profile.objects.create(user=self.employee, role="EMPLOYEE")

    def test_valid_login_opens_dashboard_and_logout_ends_session(self):
        response = self.client.post(
            "/accounts/login/",
            {"username": "qa_employee", "password": "SecurePass!234"},
        )
        self.assertRedirects(response, "/dashboard/")
        self.assertTrue(response.wsgi_request.user.is_authenticated)

        self.client.post("/accounts/logout/")
        protected = self.client.get("/dashboard/")
        self.assertEqual(protected.status_code, 302)
        self.assertIn("/accounts/login/", protected.url)

    def test_invalid_password_is_rejected(self):
        response = self.client.post(
            "/accounts/login/",
            {"username": "qa_employee", "password": "wrong-password"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_public_registration_cannot_assign_manager_role(self):
        response = self.client.post(
            "/accounts/register/",
            {
                "username": "qa_self_promoted",
                "first_name": "Taylor",
                "last_name": "Tester",
                "email": "taylor@example.test",
                "password": "SecurePass!234",
                "confirm_password": "SecurePass!234",
                "role": "MANAGER",
            },
        )
        self.assertFalse(User.objects.filter(username="qa_self_promoted").exists())
        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_change_own_role(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/accounts/profile/",
            {
                "role": "ADMIN",
                "department": "Engineering",
                "team": "QA",
                "phone": "",
                "job_title": "Tester",
                "joined_date": "",
            },
        )
        self.employee.profile.refresh_from_db()
        self.assertEqual(self.employee.profile.role, "EMPLOYEE")
        self.assertIn(response.status_code, (200, 302))

