from datetime import date
from decimal import Decimal

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.leave_management.models import LeaveBalance, LeaveRequest, LeaveType

Status = LeaveRequest.Status
INVALID = "@@INVALID"  # marker set by string_if_invalid in the test settings
LIST_URL = reverse("leave_management:list")
APPLY_URL = reverse("leave_management:apply")


def review_url(pk):
    return reverse("leave_management:review", args=[pk])


def flashed(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


class LeaveViewTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dept = Department.objects.create(name="Engineering")
        cls.hr = User.objects.create_user(email="hr@example.com", password="pw", role=User.Role.HR)
        cls.admin = User.objects.create_user(email="admin@example.com", password="pw", role=User.Role.ADMIN)
        cls.emp_user = User.objects.create_user(email="emp@example.com", password="pw", role=User.Role.EMPLOYEE)
        cls.other_user = User.objects.create_user(email="other@example.com", password="pw", role=User.Role.EMPLOYEE)
        cls.emp = Employee.objects.create(
            employee_id="E1", full_name="Asha Employee", email="e1@example.com",
            joining_date=date(2026, 1, 1), department=cls.dept, user=cls.emp_user)
        cls.other = Employee.objects.create(
            employee_id="E2", full_name="Ben Other", email="e2@example.com",
            joining_date=date(2026, 1, 1), department=cls.dept, user=cls.other_user)
        cls.hr_emp = Employee.objects.create(
            employee_id="E3", full_name="Hana HR", email="e3@example.com",
            joining_date=date(2026, 1, 1), department=cls.dept, user=cls.hr)
        cls.annual = LeaveType.objects.create(name="Annual")
        cls.old_type = LeaveType.objects.create(name="Retired", is_active=False)
        for employee in (cls.emp, cls.other, cls.hr_emp):
            LeaveBalance.objects.create(
                employee=employee, leave_type=cls.annual, year=2026,
                remaining_days=Decimal("10.00"))

    def make(self, employee, start=date(2026, 11, 16), end=date(2026, 11, 18)):
        # Mon-Wed: 3 working days
        return LeaveRequest.objects.create(
            employee=employee, leave_type=self.annual,
            start_date=start, end_date=end, reason="Trip")


class LeaveListViewTests(LeaveViewTestBase):
    def test_login_required(self):
        response = self.client.get(LIST_URL)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login/", response["Location"])

    def test_employee_sees_only_own_requests(self):
        self.make(self.emp)
        self.make(self.other, date(2026, 12, 1), date(2026, 12, 2))
        self.client.force_login(self.emp_user)
        rows = self.client.get(LIST_URL).context["page_obj"].object_list
        self.assertEqual([r["employee"] for r in rows], ["Asha Employee"])

    def test_hr_and_admin_see_everyone(self):
        self.make(self.emp)
        self.make(self.other, date(2026, 12, 1), date(2026, 12, 2))
        for user in (self.hr, self.admin):
            self.client.force_login(user)
            self.assertEqual(len(self.client.get(LIST_URL).context["page_obj"].object_list), 2)

    def test_row_matches_template_contract(self):
        leave = self.make(self.emp)
        self.client.force_login(self.emp_user)
        row = self.client.get(LIST_URL).context["page_obj"].object_list[0]
        self.assertEqual(row["id"], leave.pk)
        self.assertEqual(row["leave_type"], "Annual")
        self.assertEqual(row["start"], date(2026, 11, 16))
        self.assertEqual(row["end"], date(2026, 11, 18))
        self.assertEqual(row["days"], 3)
        # the template compares the display label: l.status == "Pending"
        self.assertEqual(row["status"], "Pending")
        self.assertEqual(row["status_code"], "PENDING")

    def test_search_and_status_filter(self):
        pending = self.make(self.emp)
        approved = self.make(self.other, date(2026, 12, 1), date(2026, 12, 2))
        LeaveRequest.objects.filter(pk=approved.pk).update(status=Status.APPROVED)
        self.client.force_login(self.hr)
        rows = self.client.get(LIST_URL, {"q": "ben"}).context["page_obj"].object_list
        self.assertEqual([r["id"] for r in rows], [approved.pk])
        rows = self.client.get(LIST_URL, {"status": "pending"}).context["page_obj"].object_list
        self.assertEqual([r["id"] for r in rows], [pending.pk])
        response = self.client.get(LIST_URL, {"status": "bogus"})
        self.assertEqual(len(response.context["page_obj"].object_list), 2)

    def test_can_apply_needs_a_profile(self):
        loner = User.objects.create_user(email="loner@example.com", password="pw")
        self.client.force_login(loner)
        self.assertFalse(self.client.get(LIST_URL).context["can_apply"])
        self.client.force_login(self.emp_user)
        self.assertTrue(self.client.get(LIST_URL).context["can_apply"])

    def test_page_renders_without_missing_template_variables(self):
        self.make(self.emp)
        for user in (self.emp_user, self.hr):
            self.client.force_login(user)
            response = self.client.get(LIST_URL)
            self.assertEqual(response.status_code, 200)
            self.assertNotIn(INVALID, response.content.decode())


class LeaveApplyViewTests(LeaveViewTestBase):
    def payload(self, **overrides):
        data = {"leave_type": str(self.annual.pk), "start": "2026-11-16",
                "end": "2026-11-18", "reason": "Family trip"}
        data.update(overrides)
        return data

    def test_form_renders_with_balances_and_active_types_only(self):
        self.client.force_login(self.emp_user)
        response = self.client.get(APPLY_URL)
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(INVALID, response.content.decode())
        self.assertEqual(response.context["balance"], {"Annual": Decimal("10.00")})
        self.assertEqual(response.context["leave_types"], [(str(self.annual.pk), "Annual")])

    def test_user_without_profile_is_redirected(self):
        self.client.force_login(self.admin)
        response = self.client.get(APPLY_URL)
        self.assertRedirects(response, LIST_URL)
        self.assertIn("Your account has no employee profile.", flashed(response))

    def test_employee_can_apply(self):
        self.client.force_login(self.emp_user)
        response = self.client.post(APPLY_URL, self.payload())
        self.assertRedirects(response, LIST_URL)
        leave = LeaveRequest.objects.get(employee=self.emp)
        self.assertEqual((leave.start_date, leave.end_date), (date(2026, 11, 16), date(2026, 11, 18)))
        self.assertEqual(leave.status, Status.PENDING)
        self.assertEqual(leave.reason, "Family trip")

    def test_cannot_apply_on_behalf_of_someone_else(self):
        self.client.force_login(self.emp_user)
        self.client.post(APPLY_URL, self.payload(employee=str(self.other.pk)))
        self.assertTrue(LeaveRequest.objects.filter(employee=self.emp).exists())
        self.assertFalse(LeaveRequest.objects.filter(employee=self.other).exists())

    def test_missing_fields_are_reported_per_field(self):
        self.client.force_login(self.emp_user)
        response = self.client.post(APPLY_URL, self.payload(leave_type="", start="", end="", reason=""))
        self.assertEqual(response.status_code, 200)
        self.assertEqual({k for k, v in response.context["errors"].items() if v},
                         {"leave_type", "start", "end", "reason"})
        self.assertFalse(LeaveRequest.objects.exists())

    def test_bad_dates_and_inactive_or_unknown_type(self):
        self.client.force_login(self.emp_user)
        response = self.client.post(APPLY_URL, self.payload(start="16/11/2026"))
        self.assertTrue(response.context["errors"]["start"])
        response = self.client.post(APPLY_URL, self.payload(leave_type=str(self.old_type.pk)))
        self.assertTrue(response.context["errors"]["leave_type"])
        response = self.client.post(APPLY_URL, self.payload(leave_type="abc"))
        self.assertTrue(response.context["errors"]["leave_type"])
        self.assertFalse(LeaveRequest.objects.exists())

    def test_service_errors_are_flashed_and_form_kept(self):
        self.client.force_login(self.emp_user)
        response = self.client.post(APPLY_URL, self.payload(start="2026-11-18", end="2026-11-16"))
        self.assertIn("Leave end date cannot be before the start date.", flashed(response))
        self.assertEqual(response.context["values"]["reason"], "Family trip")

        LeaveBalance.objects.filter(employee=self.emp).update(remaining_days=Decimal("1.00"))
        response = self.client.post(APPLY_URL, self.payload())
        self.assertIn("Insufficient leave balance for 2026.", flashed(response))
        self.assertFalse(LeaveRequest.objects.exists())

    def test_overlapping_request_is_refused(self):
        self.client.force_login(self.emp_user)
        self.client.post(APPLY_URL, self.payload())
        response = self.client.post(APPLY_URL, self.payload(start="2026-11-17", end="2026-11-19"))
        self.assertEqual(LeaveRequest.objects.filter(employee=self.emp).count(), 1)
        self.assertTrue(any("overlapping" in m for m in flashed(response)))


class LeaveReviewViewTests(LeaveViewTestBase):
    def test_employee_opens_own_request_but_not_others(self):
        mine, theirs = self.make(self.emp), self.make(self.other, date(2026, 12, 1), date(2026, 12, 2))
        self.client.force_login(self.emp_user)
        self.assertEqual(self.client.get(review_url(mine.pk)).status_code, 200)
        self.assertEqual(self.client.get(review_url(theirs.pk)).status_code, 404)
        self.assertEqual(self.client.post(review_url(theirs.pk), {"action": "cancel"}).status_code, 404)

    def test_page_matches_template_contract(self):
        leave = self.make(self.emp)
        self.client.force_login(self.hr)
        response = self.client.get(review_url(leave.pk))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(INVALID, response.content.decode())
        context = response.context
        self.assertEqual(context["leave"]["status"], "Pending")
        self.assertEqual(context["leave"]["days"], 3)
        self.assertTrue(context["can_decide"])
        self.assertTrue(context["can_cancel"])
        history = context["leave"]["history"]
        self.assertEqual([h["status"] for h in history], ["Pending"])
        self.assertEqual(history[0]["by"], "Asha Employee")  # the applicant

    def test_employee_cannot_decide_but_can_cancel(self):
        leave = self.make(self.emp)
        self.client.force_login(self.emp_user)
        context = self.client.get(review_url(leave.pk)).context
        self.assertFalse(context["can_decide"])
        self.assertTrue(context["can_cancel"])
        self.assertEqual(
            self.client.post(review_url(leave.pk), {"action": "approve", "remarks": "ok"}).status_code, 403)
        leave.refresh_from_db()
        self.assertEqual(leave.status, Status.PENDING)

    def test_hr_approves_and_balance_is_deducted(self):
        leave = self.make(self.emp)
        self.client.force_login(self.hr)
        response = self.client.post(review_url(leave.pk), {"action": "approve", "remarks": "Enjoy"})
        self.assertRedirects(response, LIST_URL)
        leave.refresh_from_db()
        self.assertEqual(leave.status, Status.APPROVED)
        self.assertEqual(leave.approver, self.hr)
        self.assertIn("Leave request approved.", flashed(response))
        self.assertEqual(LeaveBalance.objects.get(employee=self.emp).remaining_days, Decimal("7.00"))

    def test_admin_can_reject(self):
        leave = self.make(self.emp)
        self.client.force_login(self.admin)
        self.client.post(review_url(leave.pk), {"action": "reject", "remarks": "Busy period"})
        leave.refresh_from_db()
        self.assertEqual(leave.status, Status.REJECTED)

    def test_remarks_required_for_a_decision(self):
        leave = self.make(self.emp)
        self.client.force_login(self.hr)
        response = self.client.post(review_url(leave.pk), {"action": "approve", "remarks": "  "})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["errors"]["remarks"])
        leave.refresh_from_db()
        self.assertEqual(leave.status, Status.PENDING)

    def test_approval_with_too_little_balance_becomes_rejection(self):
        leave = self.make(self.emp)
        LeaveBalance.objects.filter(employee=self.emp).update(remaining_days=Decimal("1.00"))
        self.client.force_login(self.hr)
        response = self.client.post(review_url(leave.pk), {"action": "approve", "remarks": "Go"})
        leave.refresh_from_db()
        self.assertEqual(leave.status, Status.REJECTED)
        self.assertIn("Not enough leave balance, so the request was rejected.", flashed(response))

    def test_hr_cannot_decide_own_request(self):
        leave = self.make(self.hr_emp)
        self.client.force_login(self.hr)
        self.assertFalse(self.client.get(review_url(leave.pk)).context["can_decide"])
        response = self.client.post(review_url(leave.pk), {"action": "approve", "remarks": "me"})
        self.assertIn("You cannot approve or reject your own leave request.", flashed(response))
        leave.refresh_from_db()
        self.assertEqual(leave.status, Status.PENDING)

    def test_owner_cancels_pending_request(self):
        leave = self.make(self.emp)
        self.client.force_login(self.emp_user)
        response = self.client.post(review_url(leave.pk), {"action": "cancel"})
        self.assertRedirects(response, LIST_URL)
        leave.refresh_from_db()
        self.assertEqual(leave.status, Status.CANCELLED)
        self.assertIn("Leave request cancelled.", flashed(response))

    def test_decided_request_cannot_be_changed_again(self):
        leave = self.make(self.emp)
        LeaveRequest.objects.filter(pk=leave.pk).update(status=Status.APPROVED)
        self.client.force_login(self.hr)
        context = self.client.get(review_url(leave.pk)).context
        self.assertFalse(context["can_decide"])
        self.assertFalse(context["can_cancel"])
        response = self.client.post(review_url(leave.pk), {"action": "reject", "remarks": "late"})
        self.assertTrue(flashed(response))
        leave.refresh_from_db()
        self.assertEqual(leave.status, Status.APPROVED)

    def test_unknown_action(self):
        leave = self.make(self.emp)
        self.client.force_login(self.hr)
        response = self.client.post(review_url(leave.pk), {"action": "explode"})
        self.assertIn("Unknown action.", flashed(response))

    def test_history_lists_each_change(self):
        leave = self.make(self.emp)
        self.client.force_login(self.hr)
        self.client.post(review_url(leave.pk), {"action": "reject", "remarks": "Busy period"})
        history = self.client.get(review_url(leave.pk)).context["leave"]["history"]
        self.assertEqual([h["status"] for h in history], ["Pending", "Rejected"])
        self.assertEqual(history[1]["remarks"], "Busy period")

    def test_anonymous_is_sent_to_login(self):
        leave = self.make(self.emp)
        self.assertEqual(self.client.get(review_url(leave.pk)).status_code, 302)