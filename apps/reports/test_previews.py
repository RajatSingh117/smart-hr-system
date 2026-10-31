from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch

from . import stubs

User = get_user_model()


def make_user(name, role):
    email = f"{name}@example.com"
    identifier = email if User.USERNAME_FIELD == "email" else name
    user = User.objects.create_user(**{User.USERNAME_FIELD: identifier}, password="pass12345")
    user.role = role
    user.save()
    return user


PAGES = [
    "reports:preview_employee_list",
    "reports:preview_employee_form",
    "reports:preview_department_list",
    "reports:preview_department_create",
    "reports:preview_attendance_list",
    "reports:preview_attendance_summary",
    "reports:preview_attendance_correct",
    "reports:preview_leave_list",
    "reports:preview_leave_apply",
    "reports:preview_payroll_list",
    "reports:preview_my_payslips",
    "reports:preview_notification_list",
]

PAGES_WITH_ID = [
    "reports:preview_employee_detail",
    "reports:preview_employee_edit",
    "reports:preview_leave_review",
    "reports:preview_payslip_detail",
]


def url_for(name):
    return reverse(name, args=[1]) if name in PAGES_WITH_ID else reverse(name)


@override_settings(ROOT_URLCONF="apps.reports.test_urls")
@patch("apps.reports.real_data.get_leaves", new=lambda: stubs.LEAVES)
@patch("apps.reports.real_data.get_attendance", new=lambda: stubs.ATTENDANCE)
@patch("apps.reports.real_data.get_departments", new=lambda: stubs.DEPARTMENTS)
@patch("apps.reports.real_data.get_employees", new=lambda: stubs.EMPLOYEES)
class PreviewPageTests(TestCase):
    def setUp(self):
        self.user = make_user("previewadmin", "admin")

    def test_anonymous_user_is_redirected_to_login(self):
        for name in PAGES + PAGES_WITH_ID:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(url_for(name)).status_code, 302)

    def test_every_preview_page_opens_for_logged_in_user(self):
        self.client.force_login(self.user)
        for name in PAGES + PAGES_WITH_ID:
            with self.subTest(page=name):
                self.assertEqual(self.client.get(url_for(name)).status_code, 200)

    def test_missing_stub_row_gives_404(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:preview_employee_detail", args=[999]))
        self.assertEqual(response.status_code, 404)

    def test_employee_list_is_paginated(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:preview_employee_list"))
        self.assertEqual(len(response.context["page_obj"]), 5)
        self.assertEqual(response.context["page_obj"].paginator.count, 6)

    def test_employee_search_filters_rows(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:preview_employee_list"), {"q": "priya"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_leave_status_filter(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:preview_leave_list"), {"status": "Pending"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)

    def test_search_with_no_match_gives_empty_list(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:preview_employee_list"), {"q": "zzzz"})
        self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_attendance_check_redirects_back_to_list(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse("reports:preview_attendance_check"))
        self.assertRedirects(response, reverse("reports:preview_attendance_list"))

    def test_notification_unread_filter(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("reports:preview_notification_list"), {"status":"Unread"})
        self.assertEqual(response.context["page_obj"].paginator.count, 2)


class ProjectUrlConfTests(TestCase):
    """No override_settings here: uses the real config/urls.py."""

    def setUp(self):
        self.user = make_user("realurl", "admin")
        self.client.force_login(self.user)

    def test_reports_pages_open_with_project_urls(self):
        for name in PAGES + ["reports:exports"]:
            with self.subTest(name=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)

    def test_month_picker_changes_month(self):
        url = reverse("reports:preview_attendance_summary")
        response = self.client.get(url, {"month": "2026-03"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["month"], "2026-03")