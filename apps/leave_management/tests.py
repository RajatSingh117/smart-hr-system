from datetime import date

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.employees.models import Employee
from .models import LeaveRequest, LeaveStatusHistory, LeaveType
from .services import change_leave_status


class LeaveStatusTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.user = User.objects.create_user(
            email="leave_test_user@example.com",
            password="test-password-123",
        )

        # Adjust required fields if your Employee model needs more data.
        cls.employee = Employee.objects.create(
            employee_id="EMP-TEST-001",
            joining_date=date(2025, 1, 1),
        )

        cls.leave_type = LeaveType.objects.create(
            name="Test Casual Leave",
        )

    def create_leave_request(self):
        return LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 2),
            reason="Testing leave status transitions",
        )

    def test_pending_to_approved(self):
        leave = self.create_leave_request()

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            changed_by=self.user,
            remarks="Approved for testing",
        )

        leave.refresh_from_db()

        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(
            LeaveStatusHistory.objects.filter(
                leave_request=leave,
                old_status=LeaveRequest.Status.PENDING,
                new_status=LeaveRequest.Status.APPROVED,
            ).count(),
            1,
        )

    def test_pending_to_rejected(self):
        leave = self.create_leave_request()

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.REJECTED,
            changed_by=self.user,
            remarks="Rejected for testing",
        )

        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.REJECTED)

    def test_pending_to_cancelled(self):
        leave = self.create_leave_request()

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.CANCELLED,
            changed_by=self.user,
            remarks="Cancelled for testing",
        )

        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.CANCELLED)

    def test_approved_to_pending_is_rejected(self):
        leave = self.create_leave_request()

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            changed_by=self.user,
        )

        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk,
                LeaveRequest.Status.PENDING,
                changed_by=self.user,
            )

    def test_status_change_creates_one_history_entry(self):
        leave = self.create_leave_request()

        initial_count = LeaveStatusHistory.objects.filter(
            leave_request=leave
        ).count()

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            changed_by=self.user,
        )

        final_count = LeaveStatusHistory.objects.filter(
            leave_request=leave
        ).count()

        self.assertEqual(final_count - initial_count, 1)
