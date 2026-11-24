from django.contrib.auth import get_user_model
from django.test import Client, TestCase

User = get_user_model()


class DemoLoginTests(TestCase):
    def test_demo_manager_can_login_from_localhost(self):
        User.objects.create_user(username="manager", password="manager123")
        client = Client(HTTP_HOST="127.0.0.1:8000")
        response = client.post(
            "/accounts/login/",
            {"username": "manager", "password": "manager123"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/dashboard/")

    def test_demo_employee_can_login_from_0_0_0_0_host(self):
        User.objects.create_user(username="employee", password="employee123")
        client = Client(HTTP_HOST="0.0.0.0:8000")
        response = client.post(
            "/accounts/login/",
            {"username": "employee", "password": "employee123"},
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/dashboard/")
