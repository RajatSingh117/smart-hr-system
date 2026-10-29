
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.employees.models import Department, Employee
from apps.reports.navigation import ADMIN, EMPLOYEE, HR, menu_for_role

User = get_user_model()


def make_user(name, role):
    """Create a test user compatible with the configured user model."""
    email = f"{name}@example.com"
    identifier = email if User.USERNAME_FIELD == "email" else name

    user = User.objects.create_user(
        **{User.USERNAME_FIELD: identifier},
        password="TestPass123!",
    )
    user.role = role
    user.save(update_fields=["role"])
    return user


class MenuTests(TestCase):
    def labels(self, role):
        return [item["label"] for item in menu_for_role(role)]

    def test_admin_sees_audit_log(self):
        self.assertIn("Audit Log", self.labels(ADMIN))

    def test_hr_does_not_see_audit_log(self):
        self.assertNotIn("Audit Log", self.labels(HR))

    def test_employee_sees_own_payslips_not_payroll(self):
        labels = self.labels(EMPLOYEE)
        self.assertIn("My Payslips", labels)
        self.assertNotIn("Payroll", labels)
        self.assertNotIn("Employees", labels)

    def test_everyone_sees_dashboard(self):
        for role in (ADMIN, HR, EMPLOYEE):
            self.assertIn("Dashboard", self.labels(role))


class DashboardAccessTests(TestCase):
    def setUp(self):
        self.admin = make_user("admin_user", ADMIN)
        self.hr = make_user("hr_user", HR)
        self.employee = make_user("emp_user", EMPLOYEE)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("reports:admin_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_each_role_redirects_to_own_dashboard(self):
        expected = [
            (self.admin, "reports:admin_dashboard"),
            (self.hr, "reports:hr_dashboard"),
            (self.employee, "reports:employee_dashboard"),
        ]

        for user, url_name in expected:
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse("reports:dashboard"))
                self.assertRedirects(
                    response,
                    reverse(url_name),
                    fetch_redirect_response=False,
                )

    def test_each_role_can_open_own_dashboard(self):
        expected = [
            (self.admin, "reports:admin_dashboard"),
            (self.hr, "reports:hr_dashboard"),
            (self.employee, "reports:employee_dashboard"),
        ]

        for user, url_name in expected:
            with self.subTest(role=user.role):
                self.client.force_login(user)
                response = self.client.get(reverse(url_name))
                self.assertEqual(response.status_code, 200)

    def test_wrong_role_gets_403(self):
        self.client.force_login(self.employee)
        self.assertEqual(
            self.client.get(reverse("reports:admin_dashboard")).status_code,
            403,
        )
        self.assertEqual(
            self.client.get(reverse("reports:hr_dashboard")).status_code,
            403,
        )

        self.client.force_login(self.hr)
        self.assertEqual(
            self.client.get(
                reverse("reports:employee_dashboard")
            ).status_code,
            403,
        )


class ReportsDashboardTests(TestCase):
    def setUp(self):
        self.admin = make_user("reports_admin", User.Role.ADMIN)
        self.hr = make_user("reports_hr", User.Role.HR)
        self.employee_user = make_user(
            "reports_employee", User.Role.EMPLOYEE
        )

        self.department = Department.objects.create(name="Engineering")

        Employee.objects.create(
            employee_id="EMP001",
            full_name="Test Employee",
            email="reports_employee@example.com",
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
            department=self.department,
            user=self.employee_user,
        )

    def test_admin_can_view_reports(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("reports:summary"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_employees"], 1)
        self.assertEqual(response.context["active_employees"], 1)
        self.assertEqual(response.context["total_departments"], 1)

    def test_hr_can_view_reports(self):
        self.client.force_login(self.hr)
        response = self.client.get(reverse("reports:summary"))
        self.assertEqual(response.status_code, 200)

    def test_employee_is_forbidden_from_reports(self):
        self.client.force_login(self.employee_user)
        response = self.client.get(reverse("reports:summary"))
        self.assertEqual(response.status_code, 403)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(reverse("reports:summary"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)
