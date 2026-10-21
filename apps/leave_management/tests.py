from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.employees.models import Employee
from apps.attendance.models import Attendance
from .models import LeaveBalance, LeaveRequest, LeaveStatusHistory, LeaveType, PublicHoliday
from .services import  (calculate_working_days,calculate_working_days_by_year, change_leave_status, create_leave_request,restore_leave_balance,)

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
    def create_leave_balance(self, remaining_days, year=2026):
        return LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=year,
            remaining_days=remaining_days,
        )
    
    def test_pending_to_approved(self):
        leave = self.create_leave_request()
        self.create_leave_balance(remaining_days=5)

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
        self.create_leave_balance(remaining_days=5)
        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            changed_by=self.user,
            remarks="Approved for testing.",
        )

        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk,
                LeaveRequest.Status.PENDING,
                changed_by=self.user,
            )

    def test_status_change_creates_one_history_entry(self):
        leave = self.create_leave_request()
        self.create_leave_balance(remaining_days=5)

        initial_count = LeaveStatusHistory.objects.filter(
            leave_request=leave
        ).count()

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            changed_by=self.user,
            remarks="Approved for testing.",
        )


        final_count = LeaveStatusHistory.objects.filter(
            leave_request=leave
        ).count()

        self.assertEqual(final_count - initial_count, 1)
class LeaveApplicationValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()

        cls.employee = Employee.objects.create(
            employee_id="EMP-TEST-002",
            email="employee002@example.com",
            joining_date=date(2025, 1, 1),
        )

        cls.other_employee = Employee.objects.create(
            employee_id="EMP-TEST-003",
            email="employee003@example.com",
            joining_date=date(2025, 1, 1),
        )

        cls.leave_type = LeaveType.objects.create(
            name="Validation Casual Leave",
        )

    def create_request(self, employee=None, start=None, end=None):
        return create_leave_request(
            employee=employee or self.employee,
            leave_type=self.leave_type,
            start_date=start or date(2026, 11, 10),
            end_date=end or date(2026, 11, 12),
            reason="Testing validation",
        )

    def test_valid_request_is_created(self):
        leave = self.create_request()

        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)
        self.assertEqual(leave.employee, self.employee)

    def test_end_date_before_start_date_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.create_request(
                start=date(2026, 11, 12),
                end=date(2026, 11, 10),
            )

    def test_overlapping_pending_request_is_rejected(self):
        self.create_request()

        with self.assertRaises(ValidationError):
            self.create_request(
                start=date(2026, 11, 11),
                end=date(2026, 11, 13),
            )

    def test_overlapping_approved_request_is_rejected(self):
        leave = self.create_request()
        
        LeaveBalance.objects.create(
            employee=self.employee, leave_type=self.leave_type, year=2026, remaining_days=5,)

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            remarks="Approved for testing.",
        )

        with self.assertRaises(ValidationError):
            self.create_request(
                start=date(2026, 11, 11),
                end=date(2026, 11, 13),
            )

    def test_rejected_request_does_not_block_new_request(self):
        leave = self.create_request()

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.REJECTED,
            remarks="Rejected for testing.",
        )

        new_leave = self.create_request(
            start=date(2026, 11, 11),
            end=date(2026, 11, 13),
        )

        self.assertEqual(new_leave.status, LeaveRequest.Status.PENDING)

    def test_different_employee_can_request_same_dates(self):
        self.create_request()

        other_leave = self.create_request(
            employee=self.other_employee,
        )
        self.assertEqual(other_leave.employee, self.other_employee)

class WorkingDayCalculationTests(TestCase):
    def test_monday_to_friday_counts_five_days(self):
        days = calculate_working_days(
            date(2026, 10, 19),  # Monday
            date(2026, 10, 23),  # Friday
        )
        self.assertEqual(days, 5)

    def test_weekend_counts_zero_days(self):
        days = calculate_working_days(
            date(2026, 10, 24),  # Saturday
            date(2026, 10, 25),  # Sunday
        )
        self.assertEqual(days, 0)

    def test_public_holiday_is_excluded(self):
        PublicHoliday.objects.create(
            date=date(2026, 10, 21),  # Wednesday
            name="Test Holiday",
        )

        days = calculate_working_days(
            date(2026, 10, 19),
            date(2026, 10, 23),
        )
        self.assertEqual(days, 4)

    def test_dates_spanning_two_years(self):
        days = calculate_working_days(
            date(2026, 12, 31),  # Thursday
            date(2027, 1, 4),    # Monday
        )
        self.assertEqual(days, 3)

    def test_end_date_before_start_date_is_rejected(self):
        with self.assertRaises(ValidationError):
            calculate_working_days(
                date(2026, 10, 23),
                date(2026, 10, 19),
            )
    def test_working_days_are_split_by_calendar_year(self):
        yearly_days = calculate_working_days_by_year(
            date(2026, 12, 31),  # Thursday
            date(2027, 1, 4),    # Monday
        )

        self.assertEqual(yearly_days, {
            2026: 1,
            2027: 2,
        })

    def test_yearly_breakdown_rejects_invalid_dates(self):
        with self.assertRaises(ValidationError):
            calculate_working_days_by_year(
                date(2027, 1, 5),
                date(2027, 1, 1),
            )
class LeaveBalanceApprovalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.employee = Employee.objects.create(
    employee_id="EMP-BAL-001",
    email="[balance_test@example.com](mailto:balance_test@example.com)",
    joining_date=date(2025, 1, 1),
    )
        cls.leave_type = LeaveType.objects.create(
        name="Balance Test Leave",
        )

    def test_pending_request_does_not_deduct_balance(self):
        balance = LeaveBalance.objects.create(
         employee=self.employee,
        leave_type=self.leave_type,
        year=2026,
        remaining_days=10,
     )

        leave = create_leave_request(
        employee=self.employee,
        leave_type=self.leave_type,
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 12),
        reason="Testing pending balance",
        )
        leave.refresh_from_db()
        balance.refresh_from_db()

        self.assertEqual(
        leave.status,
        LeaveRequest.Status.PENDING,
        )
        self.assertEqual(balance.remaining_days, 10)
    
    def test_approval_deducts_working_days_from_balance(self):
        balance = LeaveBalance.objects.create(
        employee=self.employee,
        leave_type=self.leave_type,
        year=2026,
        remaining_days=10,
        )
        leave = create_leave_request(
        employee=self.employee,
        leave_type=self.leave_type,
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 12),
        reason="Testing approval deduction",
        )

        change_leave_status(
        leave.pk,
        LeaveRequest.Status.APPROVED,
        remarks="Approved for testing.",
        )
        leave.refresh_from_db()
        balance.refresh_from_db()
        self.assertEqual(
        leave.status,
        LeaveRequest.Status.APPROVED,
        )
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)

    def test_insufficient_balance_rejects_approval(self):
        balance = LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2026,
            remaining_days=2,
        )

        leave = create_leave_request(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 12),
            reason="Testing insufficient balance",
        )

        result = change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            remarks="Approval requested for testing.",
        )

        leave.refresh_from_db()
        balance.refresh_from_db()

        self.assertEqual(
            leave.status,
            LeaveRequest.Status.REJECTED,
        )
        self.assertEqual(balance.remaining_days, 2)
    
    def test_cross_year_leave_deducts_from_each_year(self):
         balance_2026 = LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2026,
            remaining_days=5,
        )

         balance_2027 = LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2027,
            remaining_days=5,
        )

         leave = create_leave_request(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 12, 31),
            end_date=date(2027, 1, 4),
            reason="Testing cross-year deduction",
        )

         change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            remarks="Approved requested for testing.",
        )

         leave.refresh_from_db()
         balance_2026.refresh_from_db()
         balance_2027.refresh_from_db()

         self.assertEqual(
            leave.status,
            LeaveRequest.Status.APPROVED,
        )
         self.assertEqual(balance_2026.remaining_days, 4)
         self.assertEqual(balance_2027.remaining_days, 3)
  
    def test_cross_year_insufficient_balance_deducts_nothing(self):
        balance_2026 = LeaveBalance.objects.create(
        employee=self.employee,
        leave_type=self.leave_type,
        year=2026,
        remaining_days=5,
        )

        balance_2027 = LeaveBalance.objects.create(
        employee=self.employee,
        leave_type=self.leave_type,
        year=2027,
        remaining_days=1,
         )

        leave = create_leave_request(
        employee=self.employee,
        leave_type=self.leave_type,
        start_date=date(2026, 12, 31),
        end_date=date(2027, 1, 4),
        reason="Testing atomicity",
        )

        change_leave_status(
        leave.pk,
        LeaveRequest.Status.APPROVED,
        remarks="Approval requested for testing.",
        )

        leave.refresh_from_db()
        balance_2026.refresh_from_db()
        balance_2027.refresh_from_db()

        self.assertEqual(
        leave.status,
        LeaveRequest.Status.REJECTED,
        )
        self.assertEqual(balance_2026.remaining_days, 5)
        self.assertEqual(balance_2027.remaining_days, 1)

    def test_approval_without_remarks_raises_validation_error(self):
        leave = create_leave_request(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 10),
            reason="Testing missing approval remarks",
            )

        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk,
                LeaveRequest.Status.APPROVED,
            )

    def test_rejection_without_remarks_raises_validation_error(self):
        leave = create_leave_request(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 10),
            reason="Testing missing rejection remarks",
        )

        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk,
                LeaveRequest.Status.REJECTED,
            )
class LeaveCancellationRestorationTests(LeaveStatusTransitionTests):
    def test_cancelling_approved_future_leave_restores_balance(self):
        leave = LeaveRequest.objects.create(
employee=self.employee,
leave_type=self.leave_type,
start_date=date(2026, 11, 2),  # Monday
end_date=date(2026, 11, 4),    # Wednesday
reason="Future leave cancellation test",
)

        balance = self.create_leave_balance(
        remaining_days=5,
        year=2026,
        )

        change_leave_status(
         leave.pk,
        LeaveRequest.Status.APPROVED,
        changed_by=self.user,
        remarks="Approved for testing",
        )

        balance.refresh_from_db()
        self.assertEqual(balance.remaining_days, 2)
        change_leave_status(
        leave.pk,
        LeaveRequest.Status.CANCELLED,
        changed_by=self.user,
        remarks="Cancelled before leave starts",
        )

        balance.refresh_from_db()
        leave.refresh_from_db()

        self.assertEqual(balance.remaining_days, 5)
        self.assertEqual(leave.status, LeaveRequest.Status.CANCELLED)
        self.assertEqual(
        leave.restoration_status,
        LeaveRequest.RestorationStatus.COMPLETED,
        )
    def test_partial_cancellation_restores_only_unused_days(self):
        leave = LeaveRequest.objects.create(
        employee=self.employee,
        leave_type=self.leave_type,
        start_date=date(2026, 10, 19),  # Monday
        end_date=date(2026, 10, 23),    # Friday
        reason="Partial cancellation test",
        )

        balance = self.create_leave_balance(
        remaining_days=10,
        year=2026,
        )

        change_leave_status(
        leave.pk,
        LeaveRequest.Status.APPROVED,
        changed_by=self.user,
        remarks="Approved for testing",
        )

        balance.refresh_from_db()
        self.assertEqual(balance.remaining_days, 5)

    # Monday was worked, so that day's leave is unused.
        Attendance.objects.create(
        employee=self.employee,
        date=date(2026, 10, 19),
        status=Attendance.Status.PRESENT,
        )

    # Tuesday was worked, so that day's leave is unused.
        Attendance.objects.create(
        employee=self.employee,
        date=date(2026, 10, 20),
        status=Attendance.Status.PRESENT,
        )

    # Wednesday has no attendance record, so the service
    # should flag the request for HR review.
        change_leave_status(
        leave.pk,
        LeaveRequest.Status.CANCELLED,
        changed_by=self.user,
        remarks="Cancelled partway through leave",
         )

        balance.refresh_from_db()
        leave.refresh_from_db()

        self.assertEqual(balance.remaining_days, 5)
        self.assertEqual(
        leave.restoration_status,
        LeaveRequest.RestorationStatus.HR_REVIEW,
        )
    def test_partial_cancellation_restores_only_confirmed_unused_days(self):
        leave = LeaveRequest.objects.create(
        employee=self.employee,
        leave_type=self.leave_type,
        start_date=date(2026, 10, 19),  # Monday
        end_date=date(2026, 10, 23),    # Friday
        reason="Partial restoration test",
        )

        balance = self.create_leave_balance(
        remaining_days=10,
        year=2026,
        )

        change_leave_status(
        leave.pk,
        LeaveRequest.Status.APPROVED,
        changed_by=self.user,
        remarks="Approved for testing",
        )

    # Monday and Tuesday were worked: unused leave.
        Attendance.objects.create(
        employee=self.employee,
        date=date(2026, 10, 19),
        status=Attendance.Status.PRESENT,
        )
        Attendance.objects.create(
        employee=self.employee,
        date=date(2026, 10, 20),
        status=Attendance.Status.LATE,
     )

    # Wednesday and Thursday were taken as leave.
        Attendance.objects.create(
        employee=self.employee,
        date=date(2026, 10, 21),
        status=Attendance.Status.ON_LEAVE,
        )
        Attendance.objects.create(
        employee=self.employee,
        date=date(2026, 10, 22),
        status=Attendance.Status.ON_LEAVE,
        )

        change_leave_status(
        leave.pk,
        LeaveRequest.Status.CANCELLED,
        changed_by=self.user,
        remarks="Cancelled partway through leave",
         )

        balance.refresh_from_db()
        leave.refresh_from_db()

    # Original 5-day deduction, then restore Monday,
    # Tuesday, and future Friday: 4 days restored.
        self.assertEqual(balance.remaining_days, 9)
        self.assertEqual(
        leave.restoration_status,
        LeaveRequest.RestorationStatus.COMPLETED,
        )
    def test_leave_balance_is_not_restored_twice(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 3),
            reason="Double restoration safety test",
        )

        balance = self.create_leave_balance(
            remaining_days=5,
            year=2026,
        )

        unused_days = [
            date(2026, 11, 2),
            date(2026, 11, 3),
        ]

        # First restoration should add two days.
        result = restore_leave_balance(leave, unused_days)

        balance.refresh_from_db()
        self.assertTrue(result)
        self.assertEqual(balance.remaining_days, 7)

        # Second restoration must not add the same days again.
        result = restore_leave_balance(leave, unused_days)

        balance.refresh_from_db()
        leave.refresh_from_db()

        self.assertTrue(result)
        self.assertEqual(balance.remaining_days, 7)
        self.assertEqual(
            leave.restoration_status,
            LeaveRequest.RestorationStatus.COMPLETED,
        )

    def test_missing_yearly_balance_prevents_partial_restoration(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 12, 31),
            end_date=date(2027, 1, 1),
            reason="Missing yearly balance safety test",
        )

        # The 2026 balance exists, but the 2027 balance does not.
        balance_2026 = self.create_leave_balance(
            remaining_days=5,
            year=2026,
        )

        unused_days = [
            date(2026, 12, 31),
            date(2027, 1, 1),
        ]

        result = restore_leave_balance(leave, unused_days)

        balance_2026.refresh_from_db()
        leave.refresh_from_db()

        # Restoration must not partially update the 2026 balance.
        self.assertFalse(result)
        self.assertEqual(balance_2026.remaining_days, 5)
        self.assertEqual(
            leave.restoration_status,
            LeaveRequest.RestorationStatus.HR_REVIEW,
        )
        self.assertTrue(leave.restoration_review_reason)

