from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone
from datetime import timedelta
from accounts.models import Profile
from tasks.models import Task
from scrum.models import Sprint
from notifications.models import Notification
from leave_attendance.models import LeaveBalance, Attendance

class Command(BaseCommand):
    help = "Create demo users, tasks, sprint, notifications and attendance."

    def get_user(self, username, password, first, last, role, department="Technology"):
        user, created = User.objects.get_or_create(username=username)
        user.first_name = first
        user.last_name = last
        user.email = f"{username}@example.com"
        user.set_password(password)
        user.save()
        Profile.objects.update_or_create(
            user=user,
            defaults={"role": role, "department": department, "team": "Product Team", "job_title": role.title()}
        )
        LeaveBalance.objects.get_or_create(user=user)
        return user

    def handle(self, *args, **kwargs):
        if not settings.DEBUG:
            raise CommandError("Demo data can only be created when DEBUG is enabled.")

        admin = self.get_user("admin", "admin123", "System", "Admin", "ADMIN")
        manager = self.get_user("manager", "manager123", "Project", "Manager", "MANAGER")
        employee = self.get_user("employee", "employee123", "Demo", "Employee", "EMPLOYEE")
        employee2 = self.get_user("employee2", "employee123", "Second", "Employee", "EMPLOYEE")

        Task.objects.get_or_create(
            title="Prepare project documentation",
            defaults={
                "description": "Prepare the final project documentation and screenshots.",
                "assigned_to": employee,
                "created_by": manager,
                "priority": "HIGH",
                "status": "IN_PROGRESS",
                "deadline": timezone.now() + timedelta(days=2),
            }
        )
        Task.objects.get_or_create(
            title="Test login and registration",
            defaults={
                "description": "Verify authentication, registration and role routing.",
                "assigned_to": employee2,
                "created_by": manager,
                "priority": "MEDIUM",
                "status": "TODO",
                "deadline": timezone.now() + timedelta(days=4),
            }
        )
        Task.objects.get_or_create(
            title="Create dashboard analytics",
            defaults={
                "description": "Add manager and employee productivity metrics.",
                "assigned_to": employee,
                "created_by": admin,
                "priority": "URGENT",
                "status": "COMPLETED",
                "deadline": timezone.now() - timedelta(days=1),
            }
        )

        sprint, _ = Sprint.objects.get_or_create(
            name="Sprint 1",
            defaults={
                "goal": "Build the core employee task management platform.",
                "start_date": timezone.now().date(),
                "end_date": (timezone.now() + timedelta(days=14)).date(),
                "created_by": manager,
            }
        )
        sprint.tasks.set(Task.objects.all())

        Notification.objects.get_or_create(
            user=employee,
            title="Welcome to the task manager",
            defaults={"message": "Your dashboard is ready. Check your assigned tasks and deadlines."}
        )

        Attendance.objects.get_or_create(user=employee, date=timezone.now().date(), defaults={"status": "PRESENT"})

        self.stdout.write(self.style.SUCCESS("Demo data created."))
        self.stdout.write("Admin    : admin / admin123")
        self.stdout.write("Manager  : manager / manager123")
        self.stdout.write("Employee : employee / employee123")
        self.stdout.write("Employee2: employee2 / employee123")
