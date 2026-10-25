
from datetime import date, datetime, timezone as dt_timezone

from django.db import IntegrityError, transaction
from django.test import TestCase

from apps.employees.models import Employee
from apps.attendance.models import Attendance


class AttendanceModelTests(TestCase):
    """Tests for attendance records and database constraints."""

    def setUp(self):
        self.employee = Employee.objects.create(
            employee_id="EMP-ATT-001",
            full_name="Test Employee",
            email="attendance.test@example.com",
            joining_date=date(2025, 1, 1),
        )
        self.attendance_date = date(2026, 10, 20)

    def test_attendance_creation_and_str(self):
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=self.attendance_date,
            check_in=datetime(
                2026, 10, 20, 9, 0, tzinfo=dt_timezone.utc
            ),
            check_out=datetime(
                2026, 10, 20, 17, 0, tzinfo=dt_timezone.utc
            ),
            status=Attendance.Status.PRESENT,
        )

        self.assertEqual(attendance.employee, self.employee)
        self.assertEqual(attendance.date, self.attendance_date)
        self.assertEqual(attendance.status, Attendance.Status.PRESENT)
        self.assertIn("Test Employee", str(attendance))
        self.assertIsNotNone(attendance.created_at)
        self.assertIsNotNone(attendance.updated_at)

    def test_duplicate_employee_date_is_rejected(self):
        Attendance.objects.create(
            employee=self.employee,
            date=self.attendance_date,
            status=Attendance.Status.PRESENT,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    employee=self.employee,
                    date=self.attendance_date,
                    status=Attendance.Status.LATE,
                )

    def test_checkout_before_checkin_is_rejected(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Attendance.objects.create(
                    employee=self.employee,
                    date=self.attendance_date,
                    check_in=datetime(
                        2026, 10, 20, 17, 0, tzinfo=dt_timezone.utc
                    ),
                    check_out=datetime(
                        2026, 10, 20, 9, 0, tzinfo=dt_timezone.utc
                    ),
                    status=Attendance.Status.PRESENT,
                )

    def test_missing_check_in_or_check_out_is_allowed(self):
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=self.attendance_date,
            check_in=None,
            check_out=None,
            status=Attendance.Status.ABSENT,
        )

        self.assertIsNone(attendance.check_in)
        self.assertIsNone(attendance.check_out)

    def test_attendance_ordering_is_latest_date_first(self):
        older = Attendance.objects.create(
            employee=self.employee,
            date=date(2026, 10, 19),
            status=Attendance.Status.PRESENT,
        )
        newer = Attendance.objects.create(
            employee=self.employee,
            date=date(2026, 10, 20),
            status=Attendance.Status.PRESENT,
        )

        records = list(Attendance.objects.all())

        self.assertEqual(records, [newer, older])
