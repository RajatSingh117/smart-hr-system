from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from unittest.mock import patch
from types import SimpleNamespace

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


HR_ONLY = [
    "reports:preview_employee_list",
    "reports:preview_employee_form",
    "reports:preview_department_list",
    "reports:preview_department_create",
    "reports:preview_attendance_summary",
    "reports:preview_attendance_correct",
    "reports:preview_payroll_list",
    "reports:exports",
]
HR_ONLY_WITH_ID = ["reports:preview_employee_edit", "reports:preview_leave_review"]


@override_settings(ROOT_URLCONF="apps.reports.test_urls")
@patch("apps.reports.real_data.get_leaves", new=lambda: stubs.LEAVES)
@patch("apps.reports.real_data.get_attendance", new=lambda: stubs.ATTENDANCE)
@patch("apps.reports.real_data.get_departments", new=lambda: stubs.DEPARTMENTS)
@patch("apps.reports.real_data.get_employees", new=lambda: stubs.EMPLOYEES)
class RoleAccessTests(TestCase):
    def setUp(self):
        self.admin = make_user("roleadmin", "admin")
        self.hr = make_user("rolehr", "hr")
        self.emp = make_user("roleemp", "employee")

    def test_anonymous_redirected_to_login(self):
        for name in HR_ONLY + ["reports:preview_attendance_list", "reports:preview_leave_list"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 302)
        for name in HR_ONLY_WITH_ID + ["reports:preview_employee_detail"]:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[1])).status_code, 302)

    def test_admin_and_hr_can_open_hr_pages(self):
        for user in (self.admin, self.hr):
            self.client.force_login(user)
            for name in HR_ONLY:
                with self.subTest(user=user.role, name=name):
                    self.assertEqual(self.client.get(reverse(name)).status_code, 200)
            for name in HR_ONLY_WITH_ID + ["reports:preview_employee_detail"]:
                with self.subTest(user=user.role, name=name):
                    self.assertEqual(self.client.get(reverse(name, args=[1])).status_code, 200)

    def test_employee_gets_403_on_hr_pages(self):
        self.client.force_login(self.emp)
        for name in HR_ONLY:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        for name in HR_ONLY_WITH_ID:
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name, args=[1])).status_code, 403)

    @patch("apps.reports.data_views.employee_for", new=lambda user: SimpleNamespace(pk=1))
    def test_employee_can_open_own_detail_but_not_others(self):
        self.client.force_login(self.emp)
        own = self.client.get(reverse("reports:preview_employee_detail", args=[1]))
        other = self.client.get(reverse("reports:preview_employee_detail", args=[2]))
        self.assertEqual(own.status_code, 200)
        self.assertEqual(other.status_code, 403)

    @patch("apps.reports.data_views.employee_for", new=lambda user: SimpleNamespace(pk=1))
    def test_employee_sees_only_own_attendance_and_leave(self):
        rows = [
            {"id": 1, "employee": "A", "employee_pk": 1, "date": "2026-10-01", "check_in": "09:00", "check_out": "18:00", "status": "Present"},
            {"id": 2, "employee": "B", "employee_pk": 2, "date": "2026-10-01", "check_in": "09:00", "check_out": "18:00", "status": "Present"},
        ]
        leaves = [
            {"id": 1, "employee": "A", "employee_pk": 1, "leave_type": "Casual", "start_date": "2026-10-02", "end_date": "2026-10-03", "reason": "x", "status": "Pending"},
            {"id": 2, "employee": "B", "employee_pk": 2, "leave_type": "Casual", "start_date": "2026-10-02", "end_date": "2026-10-03", "reason": "y", "status": "Pending"},
        ]
        self.client.force_login(self.emp)
        with patch("apps.reports.real_data.get_attendance", return_value=rows):
            response = self.client.get(reverse("reports:preview_attendance_list"))
            self.assertEqual(response.context["page_obj"].paginator.count, 1)
        with patch("apps.reports.real_data.get_leaves", return_value=leaves):
            response = self.client.get(reverse("reports:preview_leave_list"))
            self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.client.force_login(self.hr)
        with patch("apps.reports.real_data.get_attendance", return_value=rows):
            response = self.client.get(reverse("reports:preview_attendance_list"))
            self.assertEqual(response.context["page_obj"].paginator.count, 2)

    @patch("apps.reports.data_views.employee_for", new=lambda user: None)
    def test_employee_without_profile_sees_nothing(self):
        self.client.force_login(self.emp)
        response = self.client.get(reverse("reports:preview_attendance_list"))
        self.assertEqual(response.context["page_obj"].paginator.count, 0)