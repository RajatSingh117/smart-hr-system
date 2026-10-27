from datetime import date, timedelta
from unittest.mock import patch
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
            role=User.Role.HR,
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
    
    def test_non_hr_user_cannot_approve(self):
        employee_user = get_user_model().objects.create_user(
            email="plain@example.com", password="test-password-123",
        )
        leave = self.create_leave_request()
        self.create_leave_balance(remaining_days=5)
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk, LeaveRequest.Status.APPROVED,
                changed_by=employee_user, remarks="Trying",
            )
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)

    def test_hr_cannot_approve_own_leave(self):
        self.employee.user = self.user
        self.employee.save(update_fields=["user"])
        leave = self.create_leave_request()
        self.create_leave_balance(remaining_days=5)
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk, LeaveRequest.Status.APPROVED,
                changed_by=self.user, remarks="Self approval",
            )
    def test_employee_can_cancel_own_pending_leave(self):
        employee_user = get_user_model().objects.create_user(
            email="own_cancel@example.com",
            password="test-password-123",
        )
        self.employee.user = employee_user
        self.employee.save(update_fields=["user"])
        leave = self.create_leave_request()

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.CANCELLED,
            changed_by=employee_user,
            remarks="Plans changed",
        )

        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.CANCELLED)

    def test_invalid_transition_creates_no_history(self):
        leave = self.create_leave_request()
        change_leave_status(
            leave.pk, LeaveRequest.Status.REJECTED,
            changed_by=self.user, remarks="No",
        )
        before = LeaveStatusHistory.objects.filter(leave_request=leave).count()
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk, LeaveRequest.Status.APPROVED,
                changed_by=self.user, remarks="Again",
            )
        after = LeaveStatusHistory.objects.filter(leave_request=leave).count()
        self.assertEqual(before, after)
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.REJECTED)

    def test_cancelling_twice_is_rejected(self):
        leave = self.create_leave_request()
        change_leave_status(
            leave.pk, LeaveRequest.Status.CANCELLED,
            changed_by=self.user, remarks="First",
        )
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk, LeaveRequest.Status.CANCELLED,
                changed_by=self.user, remarks="Second",
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
    def test_approved_leave_cannot_be_cancelled(self):
        leave = self.create_leave_request()
        self.create_leave_balance(remaining_days=5)
        change_leave_status(
            leave.pk, LeaveRequest.Status.APPROVED,
            changed_by=self.user, remarks="Approved",
        )
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk, LeaveRequest.Status.CANCELLED,
                changed_by=self.user, remarks="Cancel",
            )
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)

    def test_user_cannot_cancel_another_employees_request(self):
        other_user = get_user_model().objects.create_user(
            email="other_emp@example.com", password="test-password-123",
        )
        leave = self.create_leave_request()
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk, LeaveRequest.Status.CANCELLED,
                changed_by=other_user, remarks="Not mine",
            )
        leave.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)

    def test_cancel_without_user_is_rejected(self):
        leave = self.create_leave_request()
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk, LeaveRequest.Status.CANCELLED, remarks="No user",
            )

    def test_approval_creates_audit_event_with_status_change(self):
        from django.contrib.contenttypes.models import ContentType
        from apps.accounts.models import AuditEvent

        leave = self.create_leave_request()
        self.create_leave_balance(remaining_days=5)
        change_leave_status(
            leave.pk, LeaveRequest.Status.APPROVED,
            changed_by=self.user, remarks="Approved",
        )
        event = AuditEvent.objects.get(
            actor=self.user,
            action="APPROVE",
            content_type=ContentType.objects.get_for_model(LeaveRequest),
            object_id=leave.pk,
        )
        self.assertEqual(event.changes["status"]["old"], "PENDING")
        self.assertEqual(event.changes["status"]["new"], "APPROVED")
    def test_leave_balance_is_not_restored_twice(self):
        leave = LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 3),
            reason="Double restoration safety test",
        )
        balance = self.create_leave_balance(remaining_days=5, year=2026)
        unused_days = [date(2026, 11, 2), date(2026, 11, 3)]

        result = restore_leave_balance(leave, unused_days)
        balance.refresh_from_db()
        self.assertTrue(result)
        self.assertEqual(balance.remaining_days, 7)

        result = restore_leave_balance(leave, unused_days)
        balance.refresh_from_db()
        leave.refresh_from_db()
        self.assertTrue(result)
        self.assertEqual(balance.remaining_days, 7)
        self.assertEqual(
            leave.restoration_status,
            LeaveRequest.RestorationStatus.COMPLETED,
        )

        
class LeaveApplicationValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.hr_user = User.objects.create_user(
            email="validation_hr@example.com",
            password="test-password-123",
            role=User.Role.HR,
        )

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
        for emp in (cls.employee, cls.other_employee):
            LeaveBalance.objects.create(
                employee=emp,
                leave_type=cls.leave_type,
                year=2026,
                remaining_days=20,
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
    
        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            changed_by=self.hr_user,
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
            changed_by=self.hr_user,
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
    def test_cancelled_request_does_not_block_new_request(self):
        leave = self.create_request()
        change_leave_status(
            leave.pk, LeaveRequest.Status.CANCELLED,
            changed_by=self.hr_user, remarks="Cancelled",
        )
        new_leave = self.create_request(
            start=date(2026, 11, 11), end=date(2026, 11, 13),
        )
        self.assertEqual(new_leave.status, LeaveRequest.Status.PENDING)

    def test_request_exceeding_balance_is_rejected_without_changes(self):
        balance = LeaveBalance.objects.get(employee=self.employee, year=2026)
        balance.remaining_days = 2   # 10 to 12 Nov is 3 working days
        balance.save()
        with self.assertRaises(ValidationError):
            self.create_request()
        self.assertFalse(
            LeaveRequest.objects.filter(employee=self.employee).exists()
        )
        balance.refresh_from_db()
        self.assertEqual(balance.remaining_days, 2)
    def test_request_without_balance_for_year_is_rejected(self):
        LeaveBalance.objects.filter(employee=self.employee).delete()
        with self.assertRaises(ValidationError):
            self.create_request()
    def test_terminated_employee_cannot_apply(self):
        self.employee.employment_status = Employee.EmploymentStatus.TERMINATED
        self.employee.save(update_fields=["employment_status"])
        with self.assertRaises(ValidationError):
            self.create_request()

    def test_inactive_leave_type_is_rejected(self):
        self.leave_type.is_active = False
        self.leave_type.save(update_fields=["is_active"])
        with self.assertRaises(ValidationError):
            self.create_request()
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
        User = get_user_model()
        cls.hr_user = User.objects.create_user(
            email="balance_hr@example.com",
            password="test-password-123",
            role=User.Role.HR,
        )
        cls.employee = Employee.objects.create(
            employee_id="EMP-BAL-001",
            email="balance_test@example.com",
            joining_date=date(2025, 1, 1),
        )
        cls.leave_type = LeaveType.objects.create(
            name="Balance Test Leave",
        )

    def create_balance(self, year, remaining_days):
        return LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=year,
            remaining_days=remaining_days,
        )

    def create_pending_request(self, start_date, end_date):
        # Created directly, so the approval-time checks can be tested
        # even when the submission-time balance check would reject it.
        return LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=start_date,
            end_date=end_date,
            reason="Testing leave balance",
        )

    def test_pending_request_does_not_deduct_balance(self):
        balance = self.create_balance(2026, 10)

        leave = create_leave_request(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 12),
            reason="Testing pending balance",
        )

        leave.refresh_from_db()
        balance.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.PENDING)
        self.assertEqual(balance.remaining_days, 10)

    def test_approval_deducts_working_days_from_balance(self):
        balance = self.create_balance(2026, 10)
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
            changed_by=self.hr_user,
            remarks="Approved for testing.",
        )

        leave.refresh_from_db()
        balance.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(balance.remaining_days, 7)

    def test_insufficient_balance_rejects_approval(self):
        balance = self.create_balance(2026, 2)
        leave = self.create_pending_request(
            date(2026, 11, 10), date(2026, 11, 12)
        )

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            changed_by=self.hr_user,
            remarks="Approval requested for testing.",
        )

        leave.refresh_from_db()
        balance.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.REJECTED)
        self.assertEqual(balance.remaining_days, 2)

    def test_cross_year_leave_deducts_from_each_year(self):
        balance_2026 = self.create_balance(2026, 5)
        balance_2027 = self.create_balance(2027, 5)
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
            changed_by=self.hr_user,
            remarks="Approved for testing.",
        )

        leave.refresh_from_db()
        balance_2026.refresh_from_db()
        balance_2027.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.APPROVED)
        self.assertEqual(balance_2026.remaining_days, 4)
        self.assertEqual(balance_2027.remaining_days, 3)

    def test_cross_year_insufficient_balance_deducts_nothing(self):
        balance_2026 = self.create_balance(2026, 5)
        balance_2027 = self.create_balance(2027, 1)
        leave = self.create_pending_request(
            date(2026, 12, 31), date(2027, 1, 4)
        )

        change_leave_status(
            leave.pk,
            LeaveRequest.Status.APPROVED,
            changed_by=self.hr_user,
            remarks="Approval requested for testing.",
        )

        leave.refresh_from_db()
        balance_2026.refresh_from_db()
        balance_2027.refresh_from_db()
        self.assertEqual(leave.status, LeaveRequest.Status.REJECTED)
        self.assertEqual(balance_2026.remaining_days, 5)
        self.assertEqual(balance_2027.remaining_days, 1)

    def test_approval_without_remarks_raises_validation_error(self):
        leave = self.create_pending_request(
            date(2026, 11, 10), date(2026, 11, 10)
        )
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk,
                LeaveRequest.Status.APPROVED,
                changed_by=self.hr_user,
            )

    def test_rejection_without_remarks_raises_validation_error(self):
        leave = self.create_pending_request(
            date(2026, 11, 10), date(2026, 11, 10)
        )
        with self.assertRaises(ValidationError):
            change_leave_status(
                leave.pk,
                LeaveRequest.Status.REJECTED,
                changed_by=self.hr_user,
            )
