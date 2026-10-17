from django.test import TestCase

# Create your tests here.
"""Access tests for the dashboard shells.

Once M2's User model has the `role` field, these create real users with it.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from apps.reports.navigation import ADMIN, EMPLOYEE, HR, menu_for_role

User = get_user_model()


def make_user(name, role):
    email=f"{name}@example.com"
    identifier = email if User.USERNAME_FIELD == "email" else name
    user = User.objects.create_user(**{User.USERNAME_FIELD: identifier}, password="pass12345")
    user.role = role
    user.save()
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

    def test_anonymous_is_redirected_to_login(self):
        response = self.client.get(reverse("reports:admin_dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_each_role_redirects_to_own_dashboard(self):
        expected = {
            self.admin: "reports:admin_dashboard",
            self.hr: "reports:hr_dashboard",
            self.employee: "reports:employee_dashboard",
        }
        for user, url_name in expected.items():
            self.client.force_login(user)
            response = self.client.get(reverse("reports:dashboard"))
            self.assertRedirects(response, reverse(url_name), fetch_redirect_response=False)

    def test_each_role_can_open_own_dashboard(self):
        pairs = [
            (self.admin, "reports:admin_dashboard"),
            (self.hr, "reports:hr_dashboard"),
            (self.employee, "reports:employee_dashboard"),
        ]
        for user, url_name in pairs:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse(url_name)).status_code, 200)

    def test_wrong_role_gets_403(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(reverse("reports:admin_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports:hr_dashboard")).status_code, 403)

        self.client.force_login(self.hr)
        self.assertEqual(self.client.get(reverse("reports:admin_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("reports:employee_dashboard")).status_code, 403)