
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from decimal import Decimal
from datetime import date

from apps.accounts.models import AuditEvent, User
from apps.employees.models import Department, JobTitle, Employee
from apps.payroll.models import SalaryComponent, PayrollPeriod, PayrollRecord, Payslip, NotificationLog


class AuditSignalTests(TestCase):
    def setUp(self):
        self.content_type = ContentType.objects.get_for_model(Department)

    def get_events(self, department):
        return AuditEvent.objects.filter(
            content_type=self.content_type,
            object_id=department.pk,
        )

    def test_create_department_is_audited(self):
        department = Department.objects.create(name='Engineering')

        event = self.get_events(department).get(action='CREATE')

        self.assertEqual(event.object_repr, 'Engineering')
        self.assertIsNone(event.actor)

    def test_update_department_records_changed_fields(self):
        department = Department.objects.create(name='Operations')

        department.name = 'Finance'
        department.save()

        event = self.get_events(department).get(action='UPDATE')

        self.assertEqual(
            event.changes['name'],
            {'old': 'Operations', 'new': 'Finance'},
        )

    def test_delete_department_is_audited(self):
        department = Department.objects.create(name='Research')
        department_id = department.pk

        department.delete()

        event = AuditEvent.objects.get(
            content_type=self.content_type,
            object_id=department_id,
            action='DELETE',
        )

        self.assertEqual(event.object_repr, 'Research')


class PayrollAuditSignalTests(TestCase):
    """Tests for automatic audit logging on Payroll models (M2 Week 3)."""

    def setUp(self):
        from apps.accounts.models import User
        from apps.employees.models import Department, JobTitle, Employee

        self.user = User.objects.create_user(
            email='hr@hrms.com',
            password='SecurePass123!',
            role=User.Role.HR
        )
        self.dept = Department.objects.create(name='Engineering')
        self.job = JobTitle.objects.create(title='Software Engineer')
        self.emp = Employee.objects.create(
            user=self.user,
            employee_id='EMP001',
            full_name='Test Employee',
            email='hr@hrms.com',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('50000.00'),
        )
        # Create a second employee for tests that need unique employee/period
        self.emp2 = Employee.objects.create(
            employee_id='EMP002',
            full_name='Test Employee 2',
            email='emp2@hrms.com',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('60000.00'),
        )
        self.period = PayrollPeriod.objects.create(
            name='January 2025',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )
        # Create a second period for tests that need unique period
        self.period2 = PayrollPeriod.objects.create(
            name='February 2025',
            start_date=date(2025, 2, 1),
            end_date=date(2025, 2, 28),
        )
        self.record = PayrollRecord.objects.create(
            employee=self.emp,
            payroll_period=self.period,
            basic_salary=Decimal('50000.00'),
            total_allowances=Decimal('5000.00'),
            total_deductions=Decimal('3000.00'),
        )

    def _get_events(self, obj):
        ct = ContentType.objects.get_for_model(obj)
        return AuditEvent.objects.filter(content_type=ct, object_id=obj.pk)

    def test_create_salary_component_is_audited(self):
        component = SalaryComponent.objects.create(
            name='Housing Allowance',
            component_type=SalaryComponent.ComponentType.ALLOWANCE,
            amount=Decimal('5000.00'),
        )
        event = self._get_events(component).get(action='CREATE')
        self.assertEqual(event.object_repr, 'Housing Allowance (Allowance)')
        self.assertIsNone(event.actor)

    def test_update_salary_component_is_audited(self):
        component = SalaryComponent.objects.create(
            name='Transport Allowance',
            component_type=SalaryComponent.ComponentType.ALLOWANCE,
            amount=Decimal('3000.00'),
        )
        component.amount = Decimal('4000.00')
        component.save()
        event = self._get_events(component).get(action='UPDATE')
        self.assertEqual(event.changes['amount'], {'old': '3000.00', 'new': '4000.00'})

    def test_delete_salary_component_is_audited(self):
        component = SalaryComponent.objects.create(
            name='Meal Allowance',
            component_type=SalaryComponent.ComponentType.ALLOWANCE,
            amount=Decimal('2000.00'),
        )
        component_id = component.pk
        component.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(SalaryComponent),
            object_id=component_id,
            action='DELETE',
        )
        self.assertEqual(event.object_repr, 'Meal Allowance (Allowance)')

    def test_create_payroll_period_is_audited(self):
        period = PayrollPeriod.objects.create(
            name='March 2025',
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 31),
        )
        event = self._get_events(period).get(action='CREATE')
        self.assertEqual(event.object_repr, 'March 2025')

    def test_update_payroll_period_is_audited(self):
        period = PayrollPeriod.objects.create(
            name='April 2025',
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
        )
        period.name = 'April 2025 Revised'
        period.save()
        event = self._get_events(period).get(action='UPDATE')
        self.assertEqual(event.changes['name'], {'old': 'April 2025', 'new': 'April 2025 Revised'})

    def test_delete_payroll_period_is_audited(self):
        period = PayrollPeriod.objects.create(
            name='May 2025',
            start_date=date(2025, 5, 1),
            end_date=date(2025, 5, 31),
        )
        period_id = period.pk
        period.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(PayrollPeriod),
            object_id=period_id,
            action='DELETE',
        )
        self.assertEqual(event.object_repr, 'May 2025')

    def test_create_payroll_record_is_audited(self):
        record = PayrollRecord.objects.create(
            employee=self.emp2,
            payroll_period=self.period2,
            basic_salary=Decimal('60000.00'),
            total_allowances=Decimal('6000.00'),
            total_deductions=Decimal('4000.00'),
        )
        event = self._get_events(record).get(action='CREATE')
        self.assertIn('Test Employee 2', event.object_repr)
        self.assertIn('February 2025', event.object_repr)

    def test_update_payroll_record_is_audited(self):
        record = PayrollRecord.objects.create(
            employee=self.emp2,
            payroll_period=self.period2,
            basic_salary=Decimal('60000.00'),
            total_allowances=Decimal('6000.00'),
            total_deductions=Decimal('4000.00'),
        )
        record.basic_salary = Decimal('65000.00')
        record.save()
        event = self._get_events(record).get(action='UPDATE')
        self.assertEqual(event.changes['basic_salary'], {'old': '60000.00', 'new': '65000.00'})

    def test_delete_payroll_record_is_audited(self):
        record = PayrollRecord.objects.create(
            employee=self.emp2,
            payroll_period=self.period,
            basic_salary=Decimal('60000.00'),
            total_allowances=Decimal('6000.00'),
            total_deductions=Decimal('4000.00'),
        )
        record_id = record.pk
        record.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(PayrollRecord),
            object_id=record_id,
            action='DELETE',
        )
        self.assertIn('Test Employee 2', event.object_repr)

    def test_create_payslip_is_audited(self):
        record = PayrollRecord.objects.create(
            employee=self.emp2,
            payroll_period=self.period,
            basic_salary=Decimal('60000.00'),
            total_allowances=Decimal('6000.00'),
            total_deductions=Decimal('4000.00'),
        )
        payslip = Payslip.objects.create(
            payroll_record=record,
            payslip_number='PS-202501-EMP002',
        )
        event = self._get_events(payslip).get(action='CREATE')
        self.assertEqual(event.object_repr, 'PS-202501-EMP002')

    def test_update_payslip_is_audited(self):
        record = PayrollRecord.objects.create(
            employee=self.emp2,
            payroll_period=self.period,
            basic_salary=Decimal('60000.00'),
            total_allowances=Decimal('6000.00'),
            total_deductions=Decimal('4000.00'),
        )
        payslip = Payslip.objects.create(
            payroll_record=record,
            payslip_number='PS-202501-EMP002',
        )
        payslip.status = Payslip.Status.FAILED
        payslip.save()
        event = self._get_events(payslip).get(action='UPDATE')
        self.assertEqual(event.changes['status'], {'old': 'GENERATED', 'new': 'FAILED'})

    def test_delete_payslip_is_audited(self):
        record = PayrollRecord.objects.create(
            employee=self.emp2,
            payroll_period=self.period,
            basic_salary=Decimal('60000.00'),
            total_allowances=Decimal('6000.00'),
            total_deductions=Decimal('4000.00'),
        )
        payslip = Payslip.objects.create(
            payroll_record=record,
            payslip_number='PS-202501-EMP002',
        )
        payslip_id = payslip.pk
        payslip.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(Payslip),
            object_id=payslip_id,
            action='DELETE',
        )
        self.assertEqual(event.object_repr, 'PS-202501-EMP002')

    def test_create_notification_log_is_audited(self):
        notification = NotificationLog.objects.create(
            recipient='test@example.com',
            notification_type=NotificationLog.NotificationType.LEAVE_DECISION,
            subject='Leave Request Approved',
            status=NotificationLog.Status.PENDING,
        )
        event = self._get_events(notification).get(action='CREATE')
        self.assertEqual(event.object_repr, 'LEAVE_DECISION - test@example.com (PENDING)')

    def test_update_notification_log_is_audited(self):
        notification = NotificationLog.objects.create(
            recipient='test@example.com',
            notification_type=NotificationLog.NotificationType.LEAVE_DECISION,
            subject='Leave Request Approved',
            status=NotificationLog.Status.PENDING,
        )
        notification.status = NotificationLog.Status.SENT
        notification.save()
        event = self._get_events(notification).get(action='UPDATE')
        self.assertEqual(event.changes['status'], {'old': 'PENDING', 'new': 'SENT'})

    def test_delete_notification_log_is_audited(self):
        notification = NotificationLog.objects.create(
            recipient='test@example.com',
            notification_type=NotificationLog.NotificationType.LEAVE_DECISION,
            subject='Leave Request Approved',
            status=NotificationLog.Status.PENDING,
        )
        notification_id = notification.pk
        notification.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(NotificationLog),
            object_id=notification_id,
            action='DELETE',
        )
        self.assertEqual(event.object_repr, 'LEAVE_DECISION - test@example.com (PENDING)')
