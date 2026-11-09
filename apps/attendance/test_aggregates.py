from datetime import date

from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.attendance.aggregates import get_monthly_attendance_totals,get_daily_attendance_totals, get_attendance_totals_by_department, get_monthly_attendance_trend
from apps.attendance.models import Attendance
from apps.employees.models import Department, Employee


class MonthlyAttendanceTotalsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.engineering = Department.objects.create(name="Engineering")
        cls.sales = Department.objects.create(name="Sales")
        cls.eng_employee = Employee.objects.create(
            employee_id="AGG-ATT-1",
            full_name="Engineering Employee",
            email="agg.att1@example.com",
            joining_date=date(2026, 1, 1),
            department=cls.engineering,
        )
        cls.sales_employee = Employee.objects.create(
            employee_id="AGG-ATT-2",
            full_name="Sales Employee",
            email="agg.att2@example.com",
            joining_date=date(2026, 1, 1),
            department=cls.sales,
        )

    def add(self, employee, day, status):
        return Attendance.objects.create(
            employee=employee, date=day, status=status
        )

    def test_counts_each_status_and_total_for_the_month(self):
        self.add(self.eng_employee, date(2026, 10, 1), Attendance.Status.PRESENT)
        self.add(self.sales_employee, date(2026, 10, 31), Attendance.Status.LATE)
        self.add(self.eng_employee, date(2026, 10, 15), Attendance.Status.ABSENT)
        # Outside the month: must not be counted.
        self.add(self.sales_employee, date(2026, 9, 30), Attendance.Status.PRESENT)
        self.add(self.sales_employee, date(2026, 11, 1), Attendance.Status.PRESENT)

        totals = get_monthly_attendance_totals(2026, 10)

        self.assertEqual(totals[Attendance.Status.PRESENT], 1)
        self.assertEqual(totals[Attendance.Status.LATE], 1)
        self.assertEqual(totals[Attendance.Status.ABSENT], 1)
        self.assertEqual(totals[Attendance.Status.HALF_DAY], 0)
        self.assertEqual(totals[Attendance.Status.ON_LEAVE], 0)
        self.assertEqual(totals["total_records"], 3)

    def test_filters_by_department(self):
        self.add(self.eng_employee, date(2026, 10, 5), Attendance.Status.PRESENT)
        self.add(self.sales_employee, date(2026, 10, 5), Attendance.Status.LATE)

        eng = get_monthly_attendance_totals(2026, 10, department=self.engineering)
        sales = get_monthly_attendance_totals(2026, 10, department=self.sales)

        self.assertEqual(eng["total_records"], 1)
        self.assertEqual(eng[Attendance.Status.PRESENT], 1)
        self.assertEqual(sales["total_records"], 1)
        self.assertEqual(sales[Attendance.Status.LATE], 1)

    def test_month_without_records_returns_zeros(self):
        totals = get_monthly_attendance_totals(2026, 10)
        self.assertEqual(totals["total_records"], 0)
        self.assertEqual(totals[Attendance.Status.PRESENT], 0)

    def test_invalid_month_is_rejected(self):
        for month in (0, 13):
            with self.subTest(month=month):
                with self.assertRaises(ValidationError):
                    get_monthly_attendance_totals(2026, month)

class DailyAttendanceTotalsTests(TestCase):
    def test_counts_only_the_requested_day(self):
        first = Employee.objects.create(
            employee_id="AGG-D-1", full_name="Daily One",
            email="d1@example.com", joining_date=date(2026, 1, 1),
        )
        second = Employee.objects.create(
            employee_id="AGG-D-2", full_name="Daily Two",
            email="d2@example.com", joining_date=date(2026, 1, 1),
        )
        Attendance.objects.create(
            employee=first, date=date(2026, 10, 5),
            status=Attendance.Status.PRESENT,
        )
        Attendance.objects.create(
            employee=second, date=date(2026, 10, 5),
            status=Attendance.Status.LATE,
        )
        Attendance.objects.create(
            employee=first, date=date(2026, 10, 6),
            status=Attendance.Status.PRESENT,
        )

        totals = get_daily_attendance_totals(date(2026, 10, 5))

        self.assertEqual(totals[Attendance.Status.PRESENT], 1)
        self.assertEqual(totals[Attendance.Status.LATE], 1)
        self.assertEqual(totals["total_records"], 2)

class AttendanceByDepartmentAndTrendTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.engineering = Department.objects.create(name="Engineering")
        cls.sales = Department.objects.create(name="Sales")
        cls.eng = Employee.objects.create(
            employee_id="AGG-T-1", full_name="Eng", email="t1@example.com",
            joining_date=date(2026, 1, 1), department=cls.engineering,
        )
        cls.no_dept = Employee.objects.create(
            employee_id="AGG-T-2", full_name="Loose", email="t2@example.com",
            joining_date=date(2026, 1, 1),
        )

    def test_breakdown_has_one_row_per_department(self):
        Attendance.objects.create(
            employee=self.eng, date=date(2026, 10, 5),
            status=Attendance.Status.PRESENT,
        )
        Attendance.objects.create(
            employee=self.no_dept, date=date(2026, 10, 5),
            status=Attendance.Status.LATE,
        )

        rows = get_attendance_totals_by_department(2026, 10)
        by_name = {row["department"]: row for row in rows}

        self.assertEqual(by_name["Engineering"][Attendance.Status.PRESENT], 1)
        self.assertEqual(by_name["Sales"]["total_records"], 0)
        self.assertEqual(by_name["No department"]["total_records"], 1)

    def test_trend_lists_months_oldest_first_across_a_year_end(self):
        Attendance.objects.create(
            employee=self.eng, date=date(2025, 12, 10),
            status=Attendance.Status.PRESENT,
        )

        trend = get_monthly_attendance_trend(months=3, today=date(2026, 1, 15))

        self.assertEqual(
            [row["label"] for row in trend], ["2025-11", "2025-12", "2026-01"]
        )
        self.assertEqual(trend[1][Attendance.Status.PRESENT], 1)
        self.assertEqual(trend[0]["total_records"], 0)

    def test_trend_rejects_invalid_month_counts(self):
        for months in (0, 25):
            with self.subTest(months=months):
                with self.assertRaises(ValidationError):
                    get_monthly_attendance_trend(months=months)