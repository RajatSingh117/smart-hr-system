
from datetime import date

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.employees.models import Department, Employee


class ReportsDashboardTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@example.com",
            password="TestPass123!",
            role=User.Role.ADMIN,
        )
        self.hr = User.objects.create_user(
            email="hr@example.com",
            password="TestPass123!",
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            email="employee@example.com",
            password="TestPass123!",
            role=User.Role.EMPLOYEE,
        )

        self.department = Department.objects.create(name="Engineering")

        Employee.objects.create(
            employee_id="EMP001",
            full_name="Test Employee",
            email="employee@example.com",
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
            department=self.department,
            user=self.employee_user,
        )

    def test_admin_can_view_reports(self):
        self.client.force_login(self.admin)

        response = self.client.get(reverse("reports:dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_employees"], 1)
        self.assertEqual(response.context["active_employees"], 1)
        self.assertEqual(response.context["total_departments"], 1)

    def test_hr_can_view_reports(self):
        self.client.force_login(self.hr)

        response = self.client.get(reverse("reports:dashboard"))

        self.assertEqual(response.status_code, 200)

    def test_employee_is_forbidden(self):
        self.client.force_login(self.employee_user)

        response = self.client.get(reverse("reports:dashboard"))

        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("reports:dashboard"))

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
