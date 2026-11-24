from datetime import date

from django.contrib.auth.models import User
from django.test import Client, TestCase
from django.utils import timezone

from accounts.models import Profile
from calendar_app.models import CalendarEvent
from chat.models import Message
from leave_attendance.models import Attendance, LeaveRequest
from notifications.models import Notification
from scrum.models import Sprint
from tasks.models import Task


class CollaborationWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="collab_admin", password="test-password")
        Profile.objects.create(user=self.admin, role="ADMIN")
        self.manager = User.objects.create_user(username="collab_manager", password="test-password")
        Profile.objects.create(user=self.manager, role="MANAGER", department="Engineering")
        self.employee = User.objects.create_user(username="collab_employee", password="test-password")
        Profile.objects.create(user=self.employee, role="EMPLOYEE", department="Engineering")
        self.other = User.objects.create_user(username="collab_other", password="test-password")
        Profile.objects.create(user=self.other, role="EMPLOYEE", department="Finance")
        self.engineering_task = Task.objects.create(
            title="Engineering sprint task",
            assigned_to=self.employee,
            created_by=self.manager,
        )
        self.finance_task = Task.objects.create(
            title="Finance sprint task",
            assigned_to=self.other,
            created_by=self.admin,
        )

    def test_calendar_event_creation_persists_for_authenticated_user(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/calendar/",
            {
                "title": "Sprint planning",
                "event_type": "MEETING",
                "start": "2026-11-02T09:00",
                "end": "2026-11-02T10:00",
                "description": "Planning session",
            },
        )
        event = CalendarEvent.objects.get(title="Sprint planning")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(event.created_by, self.employee)
        self.client.get("/calendar/")
        self.assertContains(self.client.get("/calendar/"), "Sprint planning")

    def test_calendar_rejects_event_end_before_start(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/calendar/",
            {
                "title": "Invalid event",
                "event_type": "MEETING",
                "start": "2026-11-02T10:00",
                "end": "2026-11-02T09:00",
                "description": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(CalendarEvent.objects.filter(title="Invalid event").exists())

    def test_calendar_requires_authentication(self):
        response = self.client.get("/calendar/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_chat_message_persists_and_is_visible_only_to_participants(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/chat/",
            {"recipient": self.manager.pk, "body": "Sprint handoff complete."},
        )
        message = Message.objects.get(body="Sprint handoff complete.")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(message.sender, self.employee)
        self.assertEqual(message.recipient, self.manager)
        self.assertContains(self.client.get("/chat/"), "Sprint handoff complete.")
        self.client.force_login(self.other)
        self.assertNotContains(self.client.get("/chat/"), "Sprint handoff complete.")

    def test_notification_read_is_post_only_and_user_scoped(self):
        own = Notification.objects.create(
            user=self.employee, title="Own update", message="Task changed."
        )
        other_user_notification = Notification.objects.create(
            user=self.other, title="Private update", message="Private."
        )
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(f"/notifications/{own.pk}/read/").status_code, 405)
        self.assertEqual(self.client.post(f"/notifications/{own.pk}/read/").status_code, 302)
        own.refresh_from_db()
        self.assertTrue(own.is_read)
        self.assertEqual(
            self.client.post(f"/notifications/{other_user_notification.pk}/read/").status_code,
            404,
        )
        other_user_notification.refresh_from_db()
        self.assertFalse(other_user_notification.is_read)

    def test_notification_list_does_not_disclose_another_users_items(self):
        Notification.objects.create(
            user=self.employee, title="Visible update", message="For employee."
        )
        Notification.objects.create(
            user=self.other, title="Private update", message="For another employee."
        )
        self.client.force_login(self.employee)
        response = self.client.get("/notifications/")
        self.assertContains(response, "Visible update")
        self.assertNotContains(response, "Private update")

    def test_employee_sprint_board_and_sprint_list_are_assignment_scoped(self):
        visible = Sprint.objects.create(
            name="Employee sprint",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 14),
            created_by=self.manager,
        )
        visible.tasks.add(self.engineering_task)
        hidden = Sprint.objects.create(
            name="Other employee sprint",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 14),
            created_by=self.manager,
        )
        hidden.tasks.add(self.finance_task)
        self.client.force_login(self.employee)
        response = self.client.get("/scrum/sprints/")
        self.assertContains(response, visible.name)
        self.assertNotContains(response, hidden.name)
        board = self.client.get("/scrum/board/")
        self.assertContains(board, self.engineering_task.title)
        self.assertNotContains(board, self.finance_task.title)

    def test_manager_sprint_board_and_list_are_department_scoped(self):
        local = Sprint.objects.create(
            name="Engineering sprint",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 14),
            created_by=self.admin,
        )
        local.tasks.add(self.engineering_task)
        foreign = Sprint.objects.create(
            name="Finance sprint",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 14),
            created_by=self.admin,
        )
        foreign.tasks.add(self.finance_task)
        self.client.force_login(self.manager)
        response = self.client.get("/scrum/sprints/")
        self.assertContains(response, local.name)
        self.assertNotContains(response, foreign.name)
        board = self.client.get("/scrum/board/")
        self.assertContains(board, self.engineering_task.title)
        self.assertNotContains(board, self.finance_task.title)

    def test_manager_can_create_sprint_for_department_task(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            "/scrum/sprints/create/",
            {
                "name": "November sprint",
                "goal": "Ship the QA flow",
                "start_date": "2026-11-01",
                "end_date": "2026-11-14",
                "tasks": [self.engineering_task.pk],
            },
        )
        sprint = Sprint.objects.get(name="November sprint")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(sprint.tasks.filter(pk=self.engineering_task.pk).exists())

    def test_manager_cannot_assign_foreign_department_task_to_sprint(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            "/scrum/sprints/create/",
            {
                "name": "Restricted sprint",
                "goal": "",
                "start_date": "2026-11-01",
                "end_date": "2026-11-14",
                "tasks": [self.finance_task.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Sprint.objects.filter(name="Restricted sprint").exists())

    def test_sprint_date_range_and_role_are_validated(self):
        self.client.force_login(self.manager)
        invalid = self.client.post(
            "/scrum/sprints/create/",
            {
                "name": "Reversed sprint",
                "goal": "",
                "start_date": "2026-11-15",
                "end_date": "2026-11-01",
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(Sprint.objects.filter(name="Reversed sprint").exists())
        self.client.force_login(self.employee)
        denied = self.client.post(
            "/scrum/sprints/create/",
            {
                "name": "Employee-created sprint",
                "start_date": "2026-11-01",
                "end_date": "2026-11-14",
            },
        )
        self.assertEqual(denied.status_code, 302)
        self.assertFalse(Sprint.objects.filter(name="Employee-created sprint").exists())

    def test_employee_check_in_check_out_and_duplicate_check_in(self):
        self.client.force_login(self.employee)
        first = self.client.post("/leave/attendance/", {"action": "check_in"})
        record = Attendance.objects.get(user=self.employee)
        original_check_in = record.check_in
        duplicate = self.client.post("/leave/attendance/", {"action": "check_in"})
        self.assertRedirects(first, "/leave/attendance/")
        self.assertRedirects(duplicate, "/leave/attendance/")
        self.assertEqual(record.date, timezone.localdate())
        self.assertIsNotNone(original_check_in)
        record.refresh_from_db()
        self.assertEqual(record.check_in, original_check_in)
        self.assertIsNone(record.check_out)

        response = self.client.post("/leave/attendance/", {"action": "check_out"})
        record.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertGreaterEqual(record.check_out, record.check_in)

    def test_attendance_form_rejects_check_out_before_check_in(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/leave/attendance/",
            {
                "user": self.employee.pk,
                "date": "2026-11-02",
                "status": "PRESENT",
                "check_in": "10:00",
                "check_out": "09:00",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Attendance.objects.filter(user=self.employee).exists())

    def test_employee_cannot_submit_arbitrary_attendance_record(self):
        self.client.force_login(self.employee)
        response = self.client.post(
            "/leave/attendance/",
            {
                "user": self.other.pk,
                "date": "2026-11-02",
                "status": "PRESENT",
                "check_in": "09:00",
                "check_out": "17:00",
            },
        )
        self.assertEqual(response.status_code, 405)
        self.assertFalse(Attendance.objects.exists())

    def test_manager_attendance_and_leave_review_are_department_scoped(self):
        local_attendance = Attendance.objects.create(
            user=self.employee, date=timezone.localdate(), status="PRESENT"
        )
        foreign_attendance = Attendance.objects.create(
            user=self.other, date=timezone.localdate(), status="PRESENT"
        )
        local_leave = LeaveRequest.objects.create(
            user=self.employee,
            leave_type="CASUAL",
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 3),
        )
        foreign_leave = LeaveRequest.objects.create(
            user=self.other,
            leave_type="CASUAL",
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 3),
        )
        self.client.force_login(self.manager)
        attendance_page = self.client.get("/leave/attendance/")
        self.assertContains(attendance_page, local_attendance.user.username)
        self.assertNotContains(attendance_page, foreign_attendance.user.username)
        self.assertNotContains(attendance_page, f'value="{self.other.pk}"')
        approval_page = self.client.get("/leave/approvals/")
        self.assertContains(approval_page, local_leave.user.username)
        self.assertNotContains(approval_page, foreign_leave.user.username)
        denied = self.client.post(f"/leave/approvals/{foreign_leave.pk}/approve/")
        foreign_leave.refresh_from_db()
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(foreign_leave.status, "PENDING")

    def test_leave_submission_requires_csrf_token(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.employee)
        page = csrf_client.get("/leave/")
        self.assertEqual(page.status_code, 200)
        csrf_token = csrf_client.cookies["csrftoken"].value
        payload = {
            "leave_type": "CASUAL",
            "start_date": "2026-11-02",
            "end_date": "2026-11-03",
            "reason": "CSRF QA",
        }
        rejected = csrf_client.post("/leave/", payload)
        self.assertEqual(rejected.status_code, 403)
        accepted = csrf_client.post(
            "/leave/", payload, HTTP_X_CSRFTOKEN=csrf_token
        )
        self.assertEqual(accepted.status_code, 302)
        self.assertTrue(LeaveRequest.objects.filter(user=self.employee).exists())
