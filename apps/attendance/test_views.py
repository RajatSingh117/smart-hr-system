from datetime import date
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.aggregates import get_monthly_attendance_by_employee
from apps.attendance.models import Attendance
from apps.employees.models import Department, Employee

Status = Attendance.Status
INVALID = "@@INVALID"  # marker set by string_if_invalid in the test settings


def flashed(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class ViewTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dept = Department.objects.create(name="Engineering")
        cls.hr = User.objects.create_user(
            email="hr@example.com", password="pw", role=User.Role.HR
        )
        cls.admin = User.objects.create_user(
            email="admin@example.com", password="pw", role=User.Role.ADMIN
        )
        cls.emp_user = User.objects.create_user(
            email="emp@example.com", password="pw", role=User.Role.EMPLOYEE
        )
        cls.other_user = User.objects.create_user(
            email="other@example.com", password="pw", role=User.Role.EMPLOYEE
        )
        cls.emp = Employee.objects.create(
            employee_id="E1", full_name="Asha Employee", email="e1@example.com",
            joining_date=date(2026, 1, 1), department=cls.dept, user=cls.emp_user,
        )
        cls.other = Employee.objects.create(
            employee_id="E2", full_name="Ben Other", email="e2@example.com",
            joining_date=date(2026, 1, 1), department=cls.dept, user=cls.other_user,
        )

    def make(self, employee, day, status=Status.PRESENT):
        return Attendance.objects.create(employee=employee, date=day, status=status)


class AttendanceListViewTests(ViewTestBase):
    url = reverse("attendance:list")

    def test_login_required(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_employee_sees_only_own_records(self):
        self.make(self.emp, date(2026, 10, 5))
        self.make(self.other, date(2026, 10, 5))
        self.client.force_login(self.emp_user)
        rows = self.client.get(self.url).context["page_obj"].object_list
        self.assertEqual([r["employee"] for r in rows], ["Asha Employee"])

    def test_hr_and_admin_see_everyone(self):
        self.make(self.emp, date(2026, 10, 5))
        self.make(self.other, date(2026, 10, 5))
        for user in (self.hr, self.admin):
            self.client.force_login(user)
            rows = self.client.get(self.url).context["page_obj"].object_list
            self.assertEqual(len(rows), 2)

    def test_search_and_status_filter(self):
        self.make(self.emp, date(2026, 10, 5), Status.LATE)
        self.make(self.other, date(2026, 10, 5), Status.PRESENT)
        self.client.force_login(self.hr)
        rows = self.client.get(self.url, {"q": "asha"}).context["page_obj"].object_list
        self.assertEqual([r["employee"] for r in rows], ["Asha Employee"])
        rows = self.client.get(self.url, {"status": "present"}).context["page_obj"].object_list
        self.assertEqual([r["employee"] for r in rows], ["Ben Other"])
        # an unknown status is ignored instead of breaking the page
        response = self.client.get(self.url, {"status": "bogus"})
        self.assertEqual(len(response.context["page_obj"].object_list), 2)
        self.assertEqual(response.context["status"], "")

    def test_row_status_is_display_label(self):
        self.make(self.emp, date(2026, 10, 5), Status.HALF_DAY)
        self.client.force_login(self.emp_user)
        row = self.client.get(self.url).context["page_obj"].object_list[0]
        self.assertEqual(row["status"], "Half-day")
        self.assertEqual(row["status_code"], "HALF_DAY")

    def test_today_card_flags(self):
        self.client.force_login(self.emp_user)
        context = self.client.get(self.url).context
        self.assertFalse(context["checked_in_today"])
        self.assertTrue(context["has_employee_profile"])

        Attendance.objects.create(
            employee=self.emp, date=timezone.localdate(),
            check_in=timezone.now(), status=Status.PRESENT,
        )
        context = self.client.get(self.url).context
        self.assertTrue(context["checked_in_today"])
        self.assertFalse(context["checked_out_today"])

    def test_user_without_profile_gets_empty_card(self):
        self.client.force_login(self.admin)
        context = self.client.get(self.url).context
        self.assertFalse(context["has_employee_profile"])
        self.assertIsNone(context["today_record"])

    def test_only_hr_role_can_correct(self):
        self.client.force_login(self.hr)
        self.assertTrue(self.client.get(self.url).context["can_correct"])
        self.client.force_login(self.admin)
        self.assertFalse(self.client.get(self.url).context["can_correct"])

    def test_page_renders_without_missing_template_variables(self):
        self.make(self.emp, date(2026, 10, 5))
        for user in (self.emp_user, self.hr):
            self.client.force_login(user)
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(INVALID, response.content.decode())


class AttendanceCheckViewTests(ViewTestBase):
    url = reverse("attendance:check")

    def test_get_is_not_allowed(self):
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(self.url).status_code, 405)

    def test_check_in_then_check_out(self):
        self.client.force_login(self.emp_user)
        response = self.client.post(self.url, {"action": "check_in"})
        self.assertRedirects(response, reverse("attendance:list"))
        record = Attendance.objects.get(employee=self.emp, date=timezone.localdate())
        self.assertIsNotNone(record.check_in)

        self.client.post(self.url, {"action": "check_out"})
        record.refresh_from_db()
        self.assertIsNotNone(record.check_out)

    def test_duplicate_check_in_shows_the_service_error(self):
        self.client.force_login(self.emp_user)
        self.client.post(self.url, {"action": "check_in"})
        response = self.client.post(self.url, {"action": "check_in"})
        self.assertIn("Attendance already exists for this employee today.", flashed(response))
        self.assertEqual(Attendance.objects.filter(employee=self.emp).count(), 1)

    def test_check_out_without_check_in_shows_error(self):
        self.client.force_login(self.emp_user)
        response = self.client.post(self.url, {"action": "check_out"})
        self.assertIn("You must check in before checking out.", flashed(response))

    def test_unknown_action_is_rejected(self):
        self.client.force_login(self.emp_user)
        response = self.client.post(self.url, {"action": "nope"})
        self.assertIn("Unknown action.", flashed(response))
        self.assertFalse(Attendance.objects.exists())

    def test_user_without_profile_cannot_check_in(self):
        self.client.force_login(self.admin)
        response = self.client.post(self.url, {"action": "check_in"})
        self.assertIn("Your account has no employee profile.", flashed(response))
        self.assertFalse(Attendance.objects.exists())

    def test_login_required(self):
        self.assertEqual(self.client.post(self.url, {"action": "check_in"}).status_code, 302)
        self.assertFalse(Attendance.objects.exists())


class MonthlySummaryViewTests(ViewTestBase):
    url = reverse("attendance:summary")

    def setUp(self):
        self.make(self.emp, date(2026, 10, 1), Status.PRESENT)
        self.make(self.emp, date(2026, 10, 2), Status.LATE)
        self.make(self.emp, date(2026, 10, 3), Status.HALF_DAY)
        self.make(self.other, date(2026, 10, 1), Status.ABSENT)
        self.make(self.other, date(2026, 9, 30), Status.PRESENT)  # other month

    def test_employee_sees_only_own_row(self):
        self.client.force_login(self.emp_user)
        context = self.client.get(self.url, {"month": "2026-10"}).context
        self.assertEqual([r["employee"] for r in context["rows"]], ["Asha Employee"])
        self.assertEqual(context["rows"][0]["present"], 1)
        self.assertEqual(context["rows"][0]["late"], 1)
        self.assertEqual(context["rows"][0]["half_day"], 1)

    def test_hr_sees_everyone_with_totals(self):
        self.client.force_login(self.hr)
        context = self.client.get(self.url, {"month": "2026-10"}).context
        self.assertEqual(len(context["rows"]), 2)
        self.assertEqual(context["totals"]["present"], 1)
        self.assertEqual(context["totals"]["absent"], 1)
        self.assertEqual(context["totals"]["on_leave"], 0)
        self.assertEqual(context["month"], "2026-10")

    def test_invalid_month_falls_back_to_current_month(self):
        self.client.force_login(self.hr)
        response = self.client.get(self.url, {"month": "garbage"})
        today = timezone.localdate()
        self.assertEqual(response.context["month"], f"{today.year}-{today.month:02d}")
        self.assertIn("Choose a valid month.", flashed(response))

    def test_user_without_profile_sees_nothing(self):
        # a login with no employee profile and no HR role sees nothing
        loner = User.objects.create_user(email="loner@example.com", password="pw")
        self.client.force_login(loner)
        self.assertEqual(self.client.get(self.url, {"month": "2026-10"}).context["rows"], [])

    def test_page_renders_without_missing_template_variables(self):
        for user in (self.emp_user, self.hr):
            self.client.force_login(user)
            response = self.client.get(self.url, {"month": "2026-10"})
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(INVALID, response.content.decode())


class AttendanceCorrectionViewTests(ViewTestBase):
    url = reverse("attendance:correct")

    def setUp(self):
        self.record = self.make(self.emp, date(2026, 10, 5), Status.ABSENT)

    def payload(self, **overrides):
        data = {
            "employee": str(self.emp.pk), "date": "2026-10-05",
            "status": "PRESENT", "reason": "Forgot to check in",
        }
        data.update(overrides)
        return data

    def test_employee_and_admin_are_forbidden(self):
        for user in (self.emp_user, self.admin):
            self.client.force_login(user)
            self.assertEqual(self.client.get(self.url).status_code, 403)
            self.assertEqual(self.client.post(self.url, self.payload()).status_code, 403)
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, Status.ABSENT)

    def test_anonymous_is_sent_to_login(self):
        self.assertEqual(self.client.get(self.url).status_code, 302)

    def test_hr_form_renders_without_missing_template_variables(self):
        self.client.force_login(self.hr)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(INVALID, response.content.decode())
        self.assertIn(("PRESENT", "Present"), response.context["statuses"])
        self.assertEqual(len(response.context["people"]), 2)

    def test_hr_can_correct(self):
        self.client.force_login(self.hr)
        response = self.client.post(self.url, self.payload())
        self.assertRedirects(response, reverse("attendance:list"))
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, Status.PRESENT)
        self.assertEqual(self.record.corrected_by, self.hr)
        self.assertEqual(self.record.correction_note, "Forgot to check in")

    def test_missing_fields_are_reported_per_field(self):
        self.client.force_login(self.hr)
        response = self.client.post(
            self.url, self.payload(employee="", date="", status="", reason="")
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            {k for k, v in response.context["errors"].items() if v},
            {"employee", "date", "status", "reason"},
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, Status.ABSENT)

    def test_no_record_for_that_date(self):
        self.client.force_login(self.hr)
        response = self.client.post(self.url, self.payload(date="2026-10-06"))
        self.assertIn("No attendance record", response.context["errors"]["date"])

    def test_invalid_status_and_unknown_employee(self):
        self.client.force_login(self.hr)
        response = self.client.post(self.url, self.payload(status="NOPE", employee="9999"))
        self.assertTrue(response.context["errors"]["status"])
        self.assertTrue(response.context["errors"]["employee"])
        response = self.client.post(self.url, self.payload(employee="abc"))
        self.assertTrue(response.context["errors"]["employee"])

    def test_service_error_is_flashed_and_form_kept(self):
        self.client.force_login(self.hr)
        with patch(
            "apps.attendance.views.correct_attendance",
            side_effect=ValidationError("Check-out time must be later than check-in time."),
        ):
            response = self.client.post(self.url, self.payload())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Check-out time must be later than check-in time.", flashed(response))
        self.assertEqual(response.context["values"]["reason"], "Forgot to check in")
        self.record.refresh_from_db()
        self.assertEqual(self.record.status, Status.ABSENT)


class MonthlyByEmployeeAggregateTests(ViewTestBase):
    def test_counts_per_employee_and_month_only(self):
        self.make(self.emp, date(2026, 10, 1), Status.PRESENT)
        self.make(self.emp, date(2026, 10, 2), Status.PRESENT)
        self.make(self.emp, date(2026, 10, 3), Status.LATE)
        self.make(self.other, date(2026, 10, 1), Status.ABSENT)
        self.make(self.other, date(2026, 11, 1), Status.PRESENT)

        rows = get_monthly_attendance_by_employee(2026, 10)
        self.assertEqual([r["employee"] for r in rows], ["Asha Employee", "Ben Other"])
        asha, ben = rows
        self.assertEqual((asha[Status.PRESENT], asha[Status.LATE], asha["total_records"]), (2, 1, 3))
        self.assertEqual((ben[Status.ABSENT], ben["total_records"]), (1, 1))
        self.assertEqual(asha[Status.ON_LEAVE], 0)

    def test_single_employee_filter(self):
        self.make(self.emp, date(2026, 10, 1))
        self.make(self.other, date(2026, 10, 1))
        rows = get_monthly_attendance_by_employee(2026, 10, employee=self.other)
        self.assertEqual([r["employee_code"] for r in rows], ["E2"])

    def test_empty_month_and_bad_month(self):
        self.assertEqual(get_monthly_attendance_by_employee(2026, 10), [])
        with self.assertRaises(ValidationError):
            get_monthly_attendance_by_employee(2026, 13)