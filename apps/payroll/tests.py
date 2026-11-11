from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test.utils import override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance
from apps.attendance.services import correct_attendance
from apps.employees.models import Employee
from apps.leave_management.models import (
    LeaveType,
    LeaveBalance,
    LeaveRequest,
)
from apps.leave_management.services import change_leave_status
from apps.payroll.models import (
    SalaryComponent,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    NotificationLog,
)
from apps.payroll.notifications import send_notification
from apps.payroll.pdf_services import generate_payslip_pdf


class SalaryComponentTest(TestCase):

    def test_create_salary_component(self):
        component = SalaryComponent.objects.create(
            name="House Rent Allowance",
            component_type=SalaryComponent.ComponentType.ALLOWANCE,
            amount=Decimal("5000.00"),
        )

        self.assertEqual(component.amount, Decimal("5000.00"))
        self.assertTrue(component.is_active)


class PayrollPeriodTest(TestCase):

    def test_create_payroll_period(self):
        period = PayrollPeriod.objects.create(
            name="October 2026",
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
        )

        self.assertEqual(period.name, "October 2026")
        self.assertFalse(period.is_processed)

    def test_end_date_cannot_be_before_start_date(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PayrollPeriod.objects.create(
                    name="Invalid Period",
                    start_date=date(2026, 11, 30),
                    end_date=date(2026, 11, 1),
                )


class PayrollRecordTest(TestCase):

    def setUp(self):
        self.employee = Employee.objects.create(
            employee_id="EMP001",
            full_name="Test Employee",
            email="test.employee@example.com",
            joining_date=date(2026, 1, 1),
            base_salary=Decimal("25000.00"),
        )

        self.period = PayrollPeriod.objects.create(
            name="November 2026",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
        )

    def test_calculate_salary_totals(self):
        record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period,
            basic_salary=Decimal("25000.00"),
            total_allowances=Decimal("5000.00"),
            total_deductions=Decimal("2000.00"),
        )

        self.assertEqual(record.gross_salary, Decimal("30000.00"))
        self.assertEqual(record.net_salary, Decimal("28000.00"))

    def test_duplicate_employee_period_is_rejected(self):
        PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period,
            basic_salary=Decimal("25000.00"),
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                PayrollRecord.objects.create(
                    employee=self.employee,
                    payroll_period=self.period,
                    basic_salary=Decimal("25000.00"),
                )


class PayslipTest(TestCase):

    def test_create_payslip(self):
        employee = Employee.objects.create(
            employee_id="EMP002",
            full_name="Another Employee",
            email="another.employee@example.com",
            joining_date=date(2026, 1, 1),
            base_salary=Decimal("30000.00"),
        )

        period = PayrollPeriod.objects.create(
            name="December 2026",
            start_date=date(2026, 12, 1),
            end_date=date(2026, 12, 31),
        )

        record = PayrollRecord.objects.create(
            employee=employee,
            payroll_period=period,
            basic_salary=Decimal("30000.00"),
        )

        payslip = Payslip.objects.create(
            payroll_record=record,
            payslip_number="PAY-2026-001",
        )

        self.assertEqual(payslip.payslip_number, "PAY-2026-001")
        self.assertEqual(payslip.status, Payslip.Status.GENERATED)


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class NotificationTest(TestCase):

    def setUp(self):
        self.recipient = "employee@example.com"

        self.context = {
            "employee_name": "Test Employee",
            "status": "Approved",
            "start_date": "2026-10-25",
            "end_date": "2026-10-27",
            "remarks": "Approved by HR",
            "attendance_date": "2026-10-23",
            "check_in": "09:00 AM",
            "check_out": "05:00 PM",
            "payroll_period": "October 2026",
            "payslip_number": "PAY-2026-001",
            "net_salary": "28000.00",
        }

    def test_notification_sent_successfully(self):
        log = send_notification(
            notification_name="leave_decision",
            recipient=self.recipient,
            context=self.context,
            subject="Leave Request Update",
        )

        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.recipient, self.recipient)
        self.assertIsNotNone(log.sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, [self.recipient])

        self.assertIn(
            "Test Employee",
            mail.outbox[0].alternatives[0][0],
        )

    @patch("apps.payroll.notifications.EmailMultiAlternatives.send")
    def test_zero_messages_sent_is_logged_as_failed(self, mock_send):
        mock_send.return_value = 0

        log = send_notification(
            notification_name="leave_decision",
            recipient=self.recipient,
            context=self.context,
            subject="Leave Request Update",
        )

        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIsNone(log.sent_at)

        self.assertEqual(
            log.error_message,
            "Email backend did not confirm sending the message.",
        )
    @patch(
        "apps.payroll.notifications.EmailMultiAlternatives.send",
        side_effect=Exception("SMTP server unavailable"),
    )
    def test_smtp_server_unavailable_is_logged_as_failed(self, mock_send):
        log = send_notification(
            notification_name="leave_decision",
            recipient=self.recipient,
            context=self.context,
            subject="Leave Request Update",
        )

        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertIsNone(log.sent_at)
        self.assertEqual(
            log.error_message,
            "Email rendering or delivery failed.",
        )

@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
)
class NotificationWorkflowTests(TestCase):

    def setUp(self):
        self.hr_user = User.objects.create_user(
            email="hr@example.com",
            password="testpassword123",
            role=User.Role.HR,
        )

        self.employee_user = User.objects.create_user(
            email="employee@example.com",
            password="testpassword123",
            role=User.Role.EMPLOYEE,
        )

        self.employee = Employee.objects.create(
            user=self.employee_user,
            employee_id="EMP-WF-001",
            full_name="Workflow Test Employee",
            email="employee@example.com",
            joining_date=date(2026, 1, 1),
        )

        self.leave_type = LeaveType.objects.create(
            name="Casual Leave",
        )

    def create_leave_request(self):
        return LeaveRequest.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            start_date=date(2026, 11, 2),
            end_date=date(2026, 11, 2),
            reason="Personal work",
        )

    def test_leave_approval_sends_notification(self):
        leave_request = self.create_leave_request()

        LeaveBalance.objects.create(
            employee=self.employee,
            leave_type=self.leave_type,
            year=2026,
            remaining_days=Decimal("5.00"),
        )

        with self.captureOnCommitCallbacks(execute=True):
            change_leave_status(
                leave_request_id=leave_request.pk,
                new_status=LeaveRequest.Status.APPROVED,
                changed_by=self.hr_user,
                remarks="Approved",
            )

        log = NotificationLog.objects.get(
            notification_type=NotificationLog.NotificationType.LEAVE_DECISION
        )

        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.recipient, self.employee.email)
        self.assertEqual(len(mail.outbox), 1)

    def test_leave_rejection_sends_notification(self):
        leave_request = self.create_leave_request()

        with self.captureOnCommitCallbacks(execute=True):
            change_leave_status(
                leave_request_id=leave_request.pk,
                new_status=LeaveRequest.Status.REJECTED,
                changed_by=self.hr_user,
                remarks="Insufficient supporting information",
            )

        log = NotificationLog.objects.get(
            notification_type=NotificationLog.NotificationType.LEAVE_DECISION
        )

        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_hr_cancellation_sends_notification(self):
        leave_request = self.create_leave_request()

        with self.captureOnCommitCallbacks(execute=True):
            change_leave_status(
                leave_request_id=leave_request.pk,
                new_status=LeaveRequest.Status.CANCELLED,
                changed_by=self.hr_user,
                remarks="Cancelled by HR",
            )

        log = NotificationLog.objects.get(
            notification_type=NotificationLog.NotificationType.LEAVE_DECISION
        )

        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

    def test_employee_cancellation_does_not_send_notification(self):
        leave_request = self.create_leave_request()

        with self.captureOnCommitCallbacks(execute=True):
            change_leave_status(
                leave_request_id=leave_request.pk,
                new_status=LeaveRequest.Status.CANCELLED,
                changed_by=self.employee_user,
                remarks="Cancelled by employee",
            )

        self.assertEqual(NotificationLog.objects.count(), 0)
        self.assertEqual(len(mail.outbox), 0)

    def test_attendance_correction_sends_notification(self):
        attendance = Attendance.objects.create(
            employee=self.employee,
            date=date(2026, 10, 30),
            check_in=timezone.now(),
            status=Attendance.Status.PRESENT,
        )

        with self.captureOnCommitCallbacks(execute=True):
            correct_attendance(
                attendance_id=attendance.pk,
                actor=self.hr_user,
                status=Attendance.Status.LATE,
                reason="Corrected by HR",
            )

        log = NotificationLog.objects.get(
            notification_type=NotificationLog.NotificationType.ATTENDANCE_UPDATE
        )

        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(log.recipient, self.employee.email)
        self.assertEqual(len(mail.outbox), 1)
class PayslipPDFGenerationTest(TestCase):

    def setUp(self):
        self.employee = Employee.objects.create(
            employee_id="EMP-PDF-001",
            full_name="PDF Test Employee",
            email="pdf.employee@example.com",
            joining_date=date(2026, 1, 1),
            base_salary=Decimal("30000.00"),
        )

        self.period = PayrollPeriod.objects.create(
            name="PDF Test Period",
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
        )

        self.payroll_record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period,
            basic_salary=Decimal("30000.00"),
            total_allowances=Decimal("5000.00"),
            total_deductions=Decimal("2000.00"),
        )

    def tearDown(self):
        # Remove generated PDF files after each test.
        payslip = Payslip.objects.filter(
            payroll_record=self.payroll_record
        ).first()

        if payslip and payslip.pdf_file:
            payslip.pdf_file.delete(save=False)

        super().tearDown()

    def test_payslip_pdf_is_generated_successfully(self):
        payslip = generate_payslip_pdf(self.payroll_record)

        self.assertEqual(
            payslip.status,
            Payslip.Status.GENERATED,
        )

        self.assertTrue(payslip.pdf_file)
        self.assertTrue(payslip.pdf_file.name.endswith(".pdf"))

        self.assertTrue(payslip.pdf_file.storage.exists(
            payslip.pdf_file.name
        ))

        # Verify that the generated file is actually a PDF.
        payslip.pdf_file.open("rb")
        pdf_header = payslip.pdf_file.read(5)
        payslip.pdf_file.close()

        self.assertEqual(pdf_header, b"%PDF-")

    @patch(
        "apps.payroll.pdf_services.SimpleDocTemplate.build",
        side_effect=Exception("PDF generation failed"),
    )
    def test_pdf_generation_failure_is_recorded(self, mock_build):
        with self.assertRaises(Exception):
            generate_payslip_pdf(self.payroll_record)

        payslip = Payslip.objects.get(
            payroll_record=self.payroll_record
        )

        self.assertEqual(
            payslip.status,
            Payslip.Status.FAILED,
        )

        self.assertFalse(payslip.pdf_file)
    def test_missing_salary_is_recorded_as_failed(self):
        self.payroll_record.basic_salary = Decimal("0.00")
        self.payroll_record.save()

        with self.assertRaisesMessage(
            ValueError,
            "Cannot generate payslip: salary is missing.",
        ):
            generate_payslip_pdf(self.payroll_record)

        payslip = Payslip.objects.get(
            payroll_record=self.payroll_record
        )

        self.assertEqual(
            payslip.status,
            Payslip.Status.FAILED,
        )
        self.assertFalse(payslip.pdf_file)