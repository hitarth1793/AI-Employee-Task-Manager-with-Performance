from datetime import date

from django.contrib.auth.models import User
from django.test import TestCase

from accounts.models import Profile
from organization.models import Department, Project, Team
from tasks.models import Task


class OrganizationWorkflowTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="org_admin", password="SecurePass!234")
        Profile.objects.create(user=self.admin, role="ADMIN")
        self.manager = User.objects.create_user(username="org_manager", password="SecurePass!234")
        Profile.objects.create(user=self.manager, role="MANAGER", department="Engineering")
        self.employee = User.objects.create_user(username="org_employee", password="SecurePass!234")
        Profile.objects.create(user=self.employee, role="EMPLOYEE")
        self.department = Department.objects.create(name="Engineering")
        self.team = Team.objects.create(name="Platform QA", department=self.department)
        self.team.members.add(self.employee)

    def test_admin_creates_unique_department_and_duplicate_is_rejected(self):
        self.client.force_login(self.admin)
        data = {"name": "Customer Success", "description": "Customer onboarding"}
        created = self.client.post("/organization/departments/create/", data)
        duplicate = self.client.post("/organization/departments/create/", data)
        self.assertEqual(created.status_code, 302)
        self.assertEqual(duplicate.status_code, 200)
        self.assertEqual(Department.objects.filter(name="Customer Success").count(), 1)

    def test_manager_cannot_create_or_delete_departments(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            "/organization/departments/create/",
            {"name": "Unauthorized", "description": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Department.objects.filter(name="Unauthorized").exists())
        denied_delete = self.client.post(
            f"/organization/departments/{self.department.pk}/delete/"
        )
        self.assertEqual(denied_delete.status_code, 302)
        self.assertTrue(Department.objects.filter(pk=self.department.pk).exists())

    def test_department_with_team_cannot_be_deleted(self):
        self.client.force_login(self.admin)
        response = self.client.post(f"/organization/departments/{self.department.pk}/delete/")
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Department.objects.filter(pk=self.department.pk).exists())

    def test_manager_creates_team_with_eligible_member_and_profile_syncs(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            "/organization/teams/create/",
            {"name": "Automation", "department": self.department.pk, "members": [self.employee.pk]},
        )
        team = Team.objects.get(name="Automation")
        self.employee.profile.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertTrue(team.members.filter(pk=self.employee.pk).exists())
        self.assertEqual(self.employee.profile.team, "Automation")
        self.assertEqual(self.employee.profile.department, "Engineering")

    def test_admin_creates_team_under_department(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/organization/teams/create/",
            {"name": "Executive Operations", "department": self.department.pk},
        )
        self.assertEqual(response.status_code, 302)
        team = Team.objects.get(name="Executive Operations")
        self.assertEqual(team.department, self.department)

    def test_repeated_team_member_submission_does_not_duplicate_membership(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            f"/organization/teams/{self.team.pk}/edit/",
            {
                "name": self.team.name,
                "department": self.department.pk,
                "members": [self.employee.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(self.team.members.filter(pk=self.employee.pk).count(), 1)

    def test_manager_cannot_create_team_in_another_department(self):
        other_department = Department.objects.create(name="Payroll")
        self.client.force_login(self.manager)
        response = self.client.post(
            "/organization/teams/create/",
            {"name": "Restricted", "department": other_department.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Team.objects.filter(name="Restricted").exists())

    def test_team_membership_can_be_removed_and_employee_scope_is_enforced(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            f"/organization/teams/{self.team.pk}/edit/",
            {"name": self.team.name, "department": self.department.pk},
        )
        self.employee.profile.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertFalse(self.team.members.filter(pk=self.employee.pk).exists())
        self.assertEqual(self.employee.profile.team, "")

    def test_member_can_view_team_roster_but_nonmember_cannot(self):
        self.client.force_login(self.employee)
        self.team.members.add(self.employee)
        self.assertEqual(self.client.get(f"/organization/teams/{self.team.pk}/").status_code, 200)
        other = User.objects.create_user(username="not_member", password="SecurePass!234")
        Profile.objects.create(user=other, role="EMPLOYEE")
        self.client.force_login(other)
        self.assertEqual(self.client.get(f"/organization/teams/{self.team.pk}/").status_code, 302)

    def test_manager_creates_project_and_invalid_date_order_is_rejected(self):
        self.client.force_login(self.manager)
        response = self.client.post(
            "/organization/projects/create/",
            {
                "name": "Workforce QA",
                "description": "Regression project",
                "team": self.team.pk,
                "start_date": "2026-10-05",
                "end_date": "2026-12-15",
                "status": "ACTIVE",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Project.objects.filter(name="Workforce QA").exists())
        invalid = self.client.post(
            "/organization/projects/create/",
            {
                "name": "Invalid range",
                "description": "",
                "team": self.team.pk,
                "start_date": "2026-12-15",
                "end_date": "2026-10-05",
                "status": "ACTIVE",
            },
        )
        self.assertEqual(invalid.status_code, 200)
        self.assertFalse(Project.objects.filter(name="Invalid range").exists())

    def test_employee_sees_only_active_projects_for_member_teams(self):
        self.team.members.add(self.employee)
        project = Project.objects.create(
            name="Team project",
            team=self.team,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 12, 15),
            created_by=self.manager,
        )
        self.client.force_login(self.employee)
        response = self.client.get("/organization/projects/")
        self.assertContains(response, project.name)
        project.status = "ARCHIVED"
        project.save()
        response = self.client.get("/organization/projects/")
        self.assertNotContains(response, project.name)

    def test_project_archive_preserves_linked_task_history(self):
        project = Project.objects.create(
            name="Archived work",
            team=self.team,
            start_date=date(2026, 10, 5),
            end_date=date(2026, 12, 15),
            created_by=self.manager,
        )
        task = Task.objects.create(
            title="Retain history",
            assigned_to=self.employee,
            created_by=self.manager,
            project=project,
        )
        self.client.force_login(self.manager)
        response = self.client.post(f"/organization/projects/{project.pk}/archive/")
        task.refresh_from_db()
        project.refresh_from_db()
        self.assertEqual(response.status_code, 302)
        self.assertEqual(project.status, "ARCHIVED")
        self.assertEqual(task.project, project)
