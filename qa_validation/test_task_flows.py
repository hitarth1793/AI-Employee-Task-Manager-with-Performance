from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Profile
from tasks.models import Task, TaskComment


class TaskFlowTests(TestCase):
    def setUp(self):
        self.manager = User.objects.create_user(username="qa_manager", password="SecurePass!234")
        Profile.objects.create(user=self.manager, role="MANAGER", department="Engineering")
        self.employee = User.objects.create_user(username="qa_employee", password="SecurePass!234")
        Profile.objects.create(user=self.employee, role="EMPLOYEE", department="Engineering")
        self.other = User.objects.create_user(username="qa_other", password="SecurePass!234")
        Profile.objects.create(user=self.other, role="EMPLOYEE", department="Engineering")
        self.task = Task.objects.create(
            title="QA workflow task",
            description="Exercise assignment and status flow.",
            assigned_to=self.employee,
            created_by=self.manager,
            priority="HIGH",
            status="TODO",
        )

    def test_manager_can_create_task_and_employee_can_read_it_back(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            "/tasks/create/",
            {
                "title": "Created by QA",
                "description": "Persistence check",
                "assigned_to": self.employee.pk,
                "priority": "MEDIUM",
                "status": "TODO",
                "deadline": "",
            },
        )
        self.assertEqual(response.status_code, 302)
        created = Task.objects.get(title="Created by QA")

        self.client.force_login(self.employee)
        response = self.client.get("/tasks/")
        self.assertContains(response, "Created by QA")
        self.assertEqual(created.assigned_to, self.employee)

    def test_employee_cannot_view_unassigned_task(self):
        self.client.force_login(self.other)
        response = self.client.get(f"/tasks/{self.task.pk}/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/tasks/", response.url)

    def test_employee_cannot_edit_unassigned_task(self):
        self.client.force_login(self.other)
        response = self.client.get(f"/tasks/{self.task.pk}/edit/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/tasks/", response.url)
        self.task.refresh_from_db()
        self.assertEqual(self.task.status, "TODO")

    def test_assigned_employee_can_add_comment_and_read_it_back(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            f"/tasks/{self.task.pk}/comment/",
            {"comment": "Verified from QA flow."},
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            TaskComment.objects.filter(
                task=self.task, user=self.employee, comment="Verified from QA flow."
            ).exists()
        )

    def test_task_comment_renders_untrusted_markup_as_text(self):
        payload = "<script>alert('xss')</script>"
        TaskComment.objects.create(task=self.task, user=self.employee, comment=payload)
        self.client.force_login(self.employee)
        response = self.client.get(f"/tasks/{self.task.pk}/")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, payload)

    def test_employee_cannot_reassign_own_task(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            f"/tasks/{self.task.pk}/edit/",
            {
                "title": self.task.title,
                "description": self.task.description,
                "assigned_to": self.other.pk,
                "priority": self.task.priority,
                "status": self.task.status,
                "deadline": "",
            },
        )
        self.task.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.task.assigned_to, self.employee)

    def test_inactive_employee_is_not_available_for_task_assignment(self):
        self.other.is_active = False
        self.other.save(update_fields=["is_active"])
        self.client.force_login(self.manager)
        response = self.client.get("/tasks/create/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'value="{self.other.pk}"')

    def test_employee_cannot_move_another_employees_kanban_card(self):
        self.client.force_login(self.other)
        response = self.client.post(
            "/tasks/kanban/update/",
            {"task_id": self.task.pk, "status": "COMPLETED"},
        )
        self.task.refresh_from_db()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.task.status, "TODO")

    def test_manager_can_move_kanban_card_and_change_is_persisted(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            "/tasks/kanban/update/",
            {"task_id": self.task.pk, "status": "IN_PROGRESS"},
        )
        self.task.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.task.status, "IN_PROGRESS")

    def test_manager_task_access_and_assignment_are_department_scoped(self):
        foreign_manager = User.objects.create_user(
            username="finance_manager", password="SecurePass!234"
        )
        Profile.objects.create(
            user=foreign_manager, role="MANAGER", department="Finance"
        )
        foreign_employee = User.objects.create_user(
            username="finance_employee", password="SecurePass!234"
        )
        Profile.objects.create(
            user=foreign_employee, role="EMPLOYEE", department="Finance"
        )
        foreign_task = Task.objects.create(
            title="Finance confidential task",
            assigned_to=foreign_employee,
            created_by=foreign_manager,
        )
        self.client.force_login(self.manager)
        task_list = self.client.get("/tasks/")
        self.assertNotContains(task_list, foreign_task.title)
        detail = self.client.get(f"/tasks/{foreign_task.pk}/")
        self.assertEqual(detail.status_code, 302)
        self.assertEqual(
            self.client.post(
                "/tasks/kanban/update/",
                {"task_id": foreign_task.pk, "status": "COMPLETED"},
            ).status_code,
            403,
        )
        create_form = self.client.get("/tasks/create/")
        self.assertNotContains(create_form, f'value="{foreign_employee.pk}"')
        foreign_task.refresh_from_db()
        self.assertEqual(foreign_task.status, "TODO")
