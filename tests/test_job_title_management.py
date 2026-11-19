from datetime import date
from django.test import TestCase, Client
from django.urls import reverse
from apps.accounts.models import User
from apps.employees.models import Department, JobTitle, Employee
from apps.employees.forms import EmployeeForm, JobTitleForm


class JobTitleManagementTests(TestCase):
    def setUp(self):
        self.password = "Secr3tP@ssw0rd!"

        self.admin = User.objects.create_user(
            email="admin@corp.com",
            password=self.password,
            role=User.Role.ADMIN,
        )
        self.hr = User.objects.create_user(
            email="hr@corp.com",
            password=self.password,
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            email="dev@corp.com",
            password=self.password,
            role=User.Role.EMPLOYEE,
        )

        self.dept = Department.objects.create(name="Engineering", is_active=True)
        self.inactive_dept = Department.objects.create(name="Archived Dept", is_active=False)

        self.title_dev = JobTitle.objects.create(title="Software Engineer", is_active=True)
        self.inactive_title = JobTitle.objects.create(title="Legacy Specialist", is_active=False)

    def test_job_title_form_validation(self):
        # Empty title invalid
        form = JobTitleForm(data={"title": "", "is_active": True})
        self.assertFalse(form.is_valid())

        # Duplicate title invalid (case-insensitive)
        form = JobTitleForm(data={"title": "software engineer", "is_active": True})
        self.assertFalse(form.is_valid())
        self.assertIn("already exists", str(form.errors["title"]))

        # Valid new title
        form = JobTitleForm(data={"title": "DevOps Engineer", "is_active": True})
        self.assertTrue(form.is_valid())

    def test_job_title_crud_views_for_admin_and_hr(self):
        client = Client()
        client.force_login(self.admin)

        # List
        resp = client.get(reverse("employees:job_title_list"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Software Engineer")

        # Create
        resp = client.post(reverse("employees:job_title_create"), {
            "title": "Product Designer",
            "description": "UI/UX lead",
            "is_active": "on",
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(JobTitle.objects.filter(title="Product Designer").exists())

        # Edit
        designer = JobTitle.objects.get(title="Product Designer")
        resp = client.post(reverse("employees:job_title_edit", kwargs={"pk": designer.pk}), {
            "title": "Senior Product Designer",
            "description": "Lead UX",
            "is_active": "on",
        })
        self.assertEqual(resp.status_code, 302)
        designer.refresh_from_db()
        self.assertEqual(designer.title, "Senior Product Designer")

        # Delete
        resp = client.post(reverse("employees:job_title_delete", kwargs={"pk": designer.pk}))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(JobTitle.objects.filter(pk=designer.pk).exists())

    def test_job_title_deletion_blocked_if_employees_assigned(self):
        emp = Employee.objects.create(
            employee_id="E099",
            full_name="Lead Dev",
            email="lead@corp.com",
            department=self.dept,
            job_title=self.title_dev,
            joining_date=date(2025, 1, 1),
        )
        client = Client()
        client.force_login(self.hr)

        resp = client.post(reverse("employees:job_title_delete", kwargs={"pk": self.title_dev.pk}))
        self.assertEqual(resp.status_code, 302)
        # Job title must NOT be deleted
        self.assertTrue(JobTitle.objects.filter(pk=self.title_dev.pk).exists())

    def test_employee_dropdown_querysets(self):
        # Fresh employee form shows only active departments and active job titles
        form = EmployeeForm()
        dept_ids = list(form.fields["department"].queryset.values_list("id", flat=True))
        title_ids = list(form.fields["job_title"].queryset.values_list("id", flat=True))

        self.assertIn(self.dept.id, dept_ids)
        self.assertNotIn(self.inactive_dept.id, dept_ids)

        self.assertIn(self.title_dev.id, title_ids)
        self.assertNotIn(self.inactive_title.id, title_ids)

        # When editing an employee already assigned to an inactive dept/title, it includes them
        emp = Employee.objects.create(
            employee_id="E100",
            full_name="Legacy Employee",
            email="legacy@corp.com",
            department=self.inactive_dept,
            job_title=self.inactive_title,
            joining_date=date(2024, 1, 1),
        )
        edit_form = EmployeeForm(instance=emp)
        edit_dept_ids = list(edit_form.fields["department"].queryset.values_list("id", flat=True))
        edit_title_ids = list(edit_form.fields["job_title"].queryset.values_list("id", flat=True))

        self.assertIn(self.inactive_dept.id, edit_dept_ids)
        self.assertIn(self.inactive_title.id, edit_title_ids)
