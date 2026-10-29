
from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.test.utils import override_settings

from apps.employees.models import Employee
from apps.payroll.models import (
    SalaryComponent,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    NotificationLog,
)
from apps.payroll.notifications import send_notification


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
    def test_notification_failure_is_logged(self, mock_send):
        mock_send.side_effect = Exception("Email delivery failed")

        log = send_notification(
            notification_name="leave_decision",
            recipient=self.recipient,
            context=self.context,
            subject="Leave Request Update",
        )

        self.assertEqual(log.status, NotificationLog.Status.FAILED)
        self.assertEqual(
            log.error_message,
            "Email rendering or delivery failed.",
        )
        self.assertIsNone(log.sent_at)

    def test_unknown_notification_type_raises_error(self):
        with self.assertRaises(ValueError):
            send_notification(
                notification_name="unknown_type",
                recipient=self.recipient,
                context=self.context,
                subject="Test",
            )

        self.assertEqual(NotificationLog.objects.count(), 0)

    def test_attendance_notification_sent_successfully(self):
        log = send_notification(
            notification_name="attendance_update",
            recipient=self.recipient,
            context=self.context,
            subject="Attendance Update",
        )

        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

        self.assertIn(
            "2026-10-23",
            mail.outbox[0].alternatives[0][0],
        )

    def test_payslip_notification_sent_successfully(self):
        log = send_notification(
            notification_name="payslip_ready",
            recipient=self.recipient,
            context=self.context,
            subject="Payslip Ready",
        )

        self.assertEqual(log.status, NotificationLog.Status.SENT)
        self.assertEqual(len(mail.outbox), 1)

        self.assertIn(
            "PAY-2026-001",
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
