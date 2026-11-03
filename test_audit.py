
"""
Audit signal tests for M2 Week 2 and Week 3.
Tests automatic audit logging for Employee, Department, JobTitle,
and Payroll models (SalaryComponent, PayrollPeriod, PayrollRecord, Payslip, NotificationLog).
"""
from django.contrib.contenttypes.models import ContentType
from django.test import TestCase
from decimal import Decimal
from datetime import date

from apps.accounts.models import AuditEvent
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
            total_allowances=Decimal('10000.00'),
            total_deductions=Decimal('5000.00'),
        )
        # Create a second record for tests that need unique record
        self.record2 = PayrollRecord.objects.create(
            employee=self.emp2,
            payroll_period=self.period2,
            basic_salary=Decimal('60000.00'),
        )
        self.payslip = Payslip.objects.create(
            payroll_record=self.record,
            payslip_number='PAY-2025-001',
        )

    def _get_events(self, model, obj_id):
        ct = ContentType.objects.get_for_model(model)
        return AuditEvent.objects.filter(content_type=ct, object_id=obj_id)

    def test_create_salary_component_is_audited(self):
        component = SalaryComponent.objects.create(
            name='HRA',
            component_type=SalaryComponent.ComponentType.ALLOWANCE,
            amount=Decimal('5000.00'),
        )
        events = self._get_events(SalaryComponent, component.pk)
        event = events.get(action='CREATE')
        self.assertEqual(event.object_repr, str(component))
        self.assertIsNone(event.actor)

    def test_update_salary_component_records_changes(self):
        component = SalaryComponent.objects.create(
            name='HRA',
            component_type=SalaryComponent.ComponentType.ALLOWANCE,
            amount=Decimal('5000.00'),
        )
        component.amount = Decimal('6000.00')
        component.save()
        events = self._get_events(SalaryComponent, component.pk)
        event = events.get(action='UPDATE')
        self.assertEqual(event.changes['amount'], {'old': '5000.00', 'new': '6000.00'})

    def test_delete_salary_component_is_audited(self):
        component = SalaryComponent.objects.create(
            name='HRA',
            component_type=SalaryComponent.ComponentType.ALLOWANCE,
            amount=Decimal('5000.00'),
        )
        cid = component.pk
        component.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(SalaryComponent),
            object_id=cid,
            action='DELETE',
        )
        self.assertEqual(event.object_repr, str(component))

    def test_create_payroll_period_is_audited(self):
        period = PayrollPeriod.objects.create(
            name='March 2025 Audit Test',
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 31),
        )
        events = self._get_events(PayrollPeriod, period.pk)
        event = events.get(action='CREATE')
        self.assertEqual(event.object_repr, 'March 2025 Audit Test')

    def test_update_payroll_period_records_changes(self):
        self.period.name = 'January 2025 Updated'
        self.period.save()
        events = self._get_events(PayrollPeriod, self.period.pk)
        event = events.get(action='UPDATE')
        self.assertEqual(event.changes['name'], {'old': 'January 2025', 'new': 'January 2025 Updated'})

    def test_delete_payroll_period_is_audited(self):
        period = PayrollPeriod.objects.create(
            name='April 2025 Audit Test',
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
        )
        pid = period.pk
        period.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(PayrollPeriod),
            object_id=pid,
            action='DELETE',
        )
        self.assertEqual(event.object_repr, 'April 2025 Audit Test')

    def test_create_payroll_record_is_audited(self):
        emp = Employee.objects.create(
            employee_id='EMP003',
            full_name='Test Employee 3',
            email='emp3@hrms.com',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('70000.00'),
        )
        period = PayrollPeriod.objects.create(
            name='March 2025 Record Test',
            start_date=date(2025, 3, 1),
            end_date=date(2025, 3, 31),
        )
        record = PayrollRecord.objects.create(
            employee=emp,
            payroll_period=period,
            basic_salary=Decimal('40000.00'),
        )
        events = self._get_events(PayrollRecord, record.pk)
        event = events.get(action='CREATE')
        self.assertIn('EMP003', event.object_repr)

    def test_update_payroll_record_salary_changes_audited(self):
        self.record.basic_salary = Decimal('55000.00')
        self.record.total_allowances = Decimal('12000.00')
        self.record.save()
        events = self._get_events(PayrollRecord, self.record.pk)
        event = events.get(action='UPDATE')
        self.assertEqual(event.changes['basic_salary'], {'old': '50000.00', 'new': '55000.00'})
        self.assertEqual(event.changes['total_allowances'], {'old': '10000.00', 'new': '12000.00'})

    def test_delete_payroll_record_is_audited(self):
        emp = Employee.objects.create(
            employee_id='EMP004',
            full_name='Test Employee 4',
            email='emp4@hrms.com',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('80000.00'),
        )
        period = PayrollPeriod.objects.create(
            name='April 2025 Record Test',
            start_date=date(2025, 4, 1),
            end_date=date(2025, 4, 30),
        )
        record = PayrollRecord.objects.create(
            employee=emp,
            payroll_period=period,
            basic_salary=Decimal('40000.00'),
        )
        rid = record.pk
        record.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(PayrollRecord),
            object_id=rid,
            action='DELETE',
        )
        self.assertIn('EMP004', event.object_repr)

    def test_create_payslip_is_audited(self):
        payslip = Payslip.objects.create(
            payroll_record=self.record2,
            payslip_number='PAY-2025-002',
        )
        events = self._get_events(Payslip, payslip.pk)
        event = events.get(action='CREATE')
        self.assertEqual(event.object_repr, 'PAY-2025-002')

    def test_update_payslip_status_audited(self):
        self.payslip.status = Payslip.Status.FAILED
        self.payslip.save()
        events = self._get_events(Payslip, self.payslip.pk)
        event = events.get(action='UPDATE')
        self.assertEqual(event.changes['status'], {'old': 'GENERATED', 'new': 'FAILED'})

    def test_delete_payslip_is_audited(self):
        payslip = Payslip.objects.create(
            payroll_record=self.record2,
            payslip_number='PAY-2025-003',
        )
        pid = payslip.pk
        payslip.delete()
        event = AuditEvent.objects.get(
            content_type=ContentType.objects.get_for_model(Payslip),
            object_id=pid,
            action='DELETE',
        )
        self.assertEqual(event.object_repr, 'PAY-2025-003')

    def test_notification_log_audited(self):
        notif = NotificationLog.objects.create(
            recipient='test@example.com',
            notification_type=NotificationLog.NotificationType.PAYSLIP_READY,
            subject='Payslip Ready',
        )
        events = self._get_events(NotificationLog, notif.pk)
        event = events.get(action='CREATE')
        self.assertEqual(event.object_repr, str(notif))
