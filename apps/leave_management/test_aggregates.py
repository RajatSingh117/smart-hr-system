from datetime import date, datetime, timedelta

from django.test import TestCase
from django.utils import timezone

from apps.employees.models import Department, Employee
from apps.leave_management.aggregates import (
    get_average_approval_hours,
    get_employee_leave_dashboard,
    get_leave_requests_by_status,
    get_pending_leave_count,
    get_employees_on_leave_count,
    get_leave_counts_by_department,
    get_monthly_leave_trend,
    
)
from apps.leave_management.models import LeaveBalance, LeaveRequest, LeaveType
from django.core.exceptions import ValidationError


Status = LeaveRequest.Status


def at(year, month, day, hour=10):
    return timezone.make_aware(datetime(year, month, day, hour, 0))


class AggregateTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.engineering = Department.objects.create(name="Engineering")
        cls.sales = Department.objects.create(name="Sales")
        cls.eng_employee = Employee.objects.create(
            employee_id="AGG-LV-1",
            full_name="Engineering Employee",
            email="agg.lv1@example.com",
            joining_date=date(2026, 1, 1),
            department=cls.engineering,
        )
        cls.sales_employee = Employee.objects.create(
            employee_id="AGG-LV-2",
            full_name="Sales Employee",
            email="agg.lv2@example.com",
            joining_date=date(2026, 1, 1),
            department=cls.sales,
        )
        cls.leave_type = LeaveType.objects.create(name="Aggregate Leave")

    def make_request(self, employee, status=Status.PENDING,
                     created=None, decided=None):
        leave = LeaveRequest.objects.create(
            employee=employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 10),
            status=status,
        )
        updates = {}
        if created is not None:
            updates["created_at"] = created
        if decided is not None:
            updates["decided_at"] = decided
        if updates:
            LeaveRequest.objects.filter(pk=leave.pk).update(**updates)
        return leave


class PendingLeaveCountTests(AggregateTestBase):
    def test_counts_only_pending_requests(self):
        self.make_request(self.eng_employee)
        self.make_request(self.sales_employee)
        self.make_request(self.eng_employee, status=Status.APPROVED)
        self.make_request(self.eng_employee, status=Status.REJECTED)
        self.make_request(self.eng_employee, status=Status.CANCELLED)

        self.assertEqual(get_pending_leave_count(), 2)

    def test_filters_by_department(self):
        self.make_request(self.eng_employee)
        self.make_request(self.eng_employee)
        self.make_request(self.sales_employee)

        self.assertEqual(get_pending_leave_count(department=self.engineering), 2)
        self.assertEqual(get_pending_leave_count(department=self.sales), 1)

    def test_filters_by_submission_period_inclusive(self):
        self.make_request(self.eng_employee, created=at(2026, 10, 5))
        self.make_request(self.eng_employee, created=at(2026, 10, 20))

        self.assertEqual(
            get_pending_leave_count(
                start_date=date(2026, 10, 1), end_date=date(2026, 10, 10)
            ),
            1,
        )
        self.assertEqual(
            get_pending_leave_count(
                start_date=date(2026, 10, 5), end_date=date(2026, 10, 20)
            ),
            2,
        )


class AverageApprovalTimeTests(AggregateTestBase):
    def test_average_of_decided_requests_in_hours(self):
        base = at(2026, 10, 5)
        self.make_request(
            self.eng_employee, Status.APPROVED,
            created=base, decided=base + timedelta(hours=2),
        )
        self.make_request(
            self.eng_employee, Status.REJECTED,
            created=base, decided=base + timedelta(hours=4),
        )
        # Not decided, or not a decision: must be ignored.
        self.make_request(self.eng_employee, Status.PENDING, created=base)
        self.make_request(
            self.eng_employee, Status.CANCELLED,
            created=base, decided=base + timedelta(hours=100),
        )

        self.assertEqual(get_average_approval_hours(), 3.0)

    def test_returns_none_without_decided_requests(self):
        self.make_request(self.eng_employee)
        self.assertIsNone(get_average_approval_hours())

    def test_filters_by_department(self):
        base = at(2026, 10, 5)
        self.make_request(
            self.eng_employee, Status.APPROVED,
            created=base, decided=base + timedelta(hours=2),
        )
        self.make_request(
            self.sales_employee, Status.APPROVED,
            created=base, decided=base + timedelta(hours=6),
        )

        self.assertEqual(get_average_approval_hours(department=self.engineering), 2.0)
        self.assertEqual(get_average_approval_hours(department=self.sales), 6.0)

    def test_filters_by_decision_period(self):
        early = at(2026, 10, 5)
        late = at(2026, 10, 20)
        self.make_request(
            self.eng_employee, Status.APPROVED,
            created=early, decided=early + timedelta(hours=2),
        )
        self.make_request(
            self.eng_employee, Status.APPROVED,
            created=late, decided=late + timedelta(hours=8),
        )

        self.assertEqual(
            get_average_approval_hours(
                start_date=date(2026, 10, 1), end_date=date(2026, 10, 10)
            ),
            2.0,
        )
        self.assertEqual(
            get_average_approval_hours(
                start_date=date(2026, 10, 15), end_date=date(2026, 10, 31)
            ),
            8.0,
        )


class LeaveRequestsByStatusTests(AggregateTestBase):
    def test_counts_each_status_with_zeros_and_total(self):
        self.make_request(self.eng_employee, Status.PENDING)
        self.make_request(self.eng_employee, Status.APPROVED)
        self.make_request(self.sales_employee, Status.APPROVED)
        self.make_request(self.sales_employee, Status.REJECTED)

        counts = get_leave_requests_by_status()

        self.assertEqual(counts[Status.PENDING], 1)
        self.assertEqual(counts[Status.APPROVED], 2)
        self.assertEqual(counts[Status.REJECTED], 1)
        self.assertEqual(counts[Status.CANCELLED], 0)
        self.assertEqual(counts["total"], 4)


class EmployeeLeaveDashboardTests(AggregateTestBase):
    def test_returns_only_the_employees_own_data(self):
        LeaveBalance.objects.create(
            employee=self.eng_employee, leave_type=self.leave_type,
            year=2026, remaining_days=12,
        )
        LeaveBalance.objects.create(
            employee=self.eng_employee, leave_type=self.leave_type,
            year=2025, remaining_days=9,
        )
        LeaveBalance.objects.create(
            employee=self.sales_employee, leave_type=self.leave_type,
            year=2026, remaining_days=3,
        )
        self.make_request(self.eng_employee)
        self.make_request(self.eng_employee, Status.APPROVED)
        self.make_request(self.sales_employee)

        data = get_employee_leave_dashboard(self.eng_employee, 2026)

        self.assertEqual(len(data["balances"]), 1)
        self.assertEqual(data["balances"][0]["remaining_days"], 12)
        self.assertEqual(data["pending_count"], 1)
        self.assertEqual(len(data["recent_requests"]), 2)

    def test_recent_requests_are_limited_and_newest_first(self):
        self.make_request(self.eng_employee)
        second = self.make_request(self.eng_employee)
        third = self.make_request(self.eng_employee)

        data = get_employee_leave_dashboard(
            self.eng_employee, 2026, recent_limit=2
        )

        self.assertEqual(
            [item["id"] for item in data["recent_requests"]],
            [third.pk, second.pk],
        )

class EmployeesOnLeaveTests(AggregateTestBase):
    def make_leave(self, employee, status, start, end):
        return LeaveRequest.objects.create(
            employee=employee, leave_type=self.leave_type,
            start_date=start, end_date=end, status=status,
        )

    def test_counts_only_approved_leave_covering_the_date(self):
        self.make_leave(
            self.eng_employee, Status.APPROVED,
            date(2026, 11, 9), date(2026, 11, 11),
        )
        self.make_leave(
            self.sales_employee, Status.PENDING,
            date(2026, 11, 9), date(2026, 11, 11),
        )

        self.assertEqual(get_employees_on_leave_count(date(2026, 11, 10)), 1)
        self.assertEqual(get_employees_on_leave_count(date(2026, 11, 12)), 0)

    def test_filters_by_department(self):
        self.make_leave(
            self.eng_employee, Status.APPROVED,
            date(2026, 11, 10), date(2026, 11, 10),
        )
        self.make_leave(
            self.sales_employee, Status.APPROVED,
            date(2026, 11, 10), date(2026, 11, 10),
        )

        self.assertEqual(
            get_employees_on_leave_count(
                date(2026, 11, 10), department=self.engineering
            ),
            1,
        )

class LeaveBreakdownAndTrendTests(AggregateTestBase):
    def test_department_breakdown_counts_statuses(self):
        self.make_request(self.eng_employee, Status.PENDING)
        self.make_request(self.eng_employee, Status.APPROVED)
        self.make_request(self.sales_employee, Status.REJECTED)

        rows = get_leave_counts_by_department()
        by_name = {row["department"]: row for row in rows}

        self.assertEqual(by_name["Engineering"][Status.PENDING], 1)
        self.assertEqual(by_name["Engineering"]["total"], 2)
        self.assertEqual(by_name["Sales"][Status.REJECTED], 1)

    def test_monthly_trend_counts_by_submission_month(self):
        self.make_request(self.eng_employee, Status.PENDING, created=at(2026, 9, 10))
        self.make_request(self.eng_employee, Status.APPROVED, created=at(2026, 10, 20))
        self.make_request(self.sales_employee, Status.APPROVED, created=at(2026, 10, 21))

        trend = get_monthly_leave_trend(months=3, today=date(2026, 10, 25))

        self.assertEqual(
            [row["label"] for row in trend], ["2026-08", "2026-09", "2026-10"]
        )
        self.assertEqual(trend[0]["total"], 0)
        self.assertEqual(trend[1][Status.PENDING], 1)
        self.assertEqual(trend[2][Status.APPROVED], 2)

    def test_trend_rejects_invalid_month_counts(self):
        for months in (0, 25):
            with self.subTest(months=months):
                with self.assertRaises(ValidationError):
                    get_monthly_leave_trend(months=months)