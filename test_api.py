from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.payroll.models import (
    SalaryComponent,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    NotificationLog,
)
from apps.payroll.notifications import send_notification


def make_user(email, role, password="TestPass123!"):
    """Create a test user."""
    user = User.objects.create_user(email=email, password=password)
    user.role = role
    user.save(update_fields=["role"])
    return user


class PayrollAPITestBase(TestCase):
    """Base class with common test setup."""

    def setUp(self):
        self.client = APIClient()

        # Create users
        self.admin = make_user("admin@test.com", User.Role.ADMIN)
        self.hr = make_user("hr@test.com", User.Role.HR)
        self.employee_user = make_user("employee@test.com", User.Role.EMPLOYEE)
        self.employee_user2 = make_user("employee2@test.com", User.Role.EMPLOYEE)

        # Create department
        self.department = Department.objects.create(name="Engineering")

        # Create employees
        self.employee = Employee.objects.create(
            user=self.employee_user,
            employee_id="EMP001",
            full_name="Test Employee",
            email="employee@test.com",
            joining_date=date(2026, 1, 1),
            base_salary=Decimal("50000.00"),
            department=self.department,
        )
        self.employee2 = Employee.objects.create(
            user=self.employee_user2,
            employee_id="EMP002",
            full_name="Test Employee 2",
            email="employee2@test.com",
            joining_date=date(2026, 1, 1),
            base_salary=Decimal("60000.00"),
            department=self.department,
        )

        # Create payroll period
        self.period = PayrollPeriod.objects.create(
            name="January 2026",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
        )

        # Create payroll records
        self.record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period,
            basic_salary=Decimal("50000.00"),
            total_allowances=Decimal("5000.00"),
            total_deductions=Decimal("3000.00"),
        )
        self.record2 = PayrollRecord.objects.create(
            employee=self.employee2,
            payroll_period=self.period,
            basic_salary=Decimal("60000.00"),
            total_allowances=Decimal("6000.00"),
            total_deductions=Decimal("4000.00"),
        )

        # Create payslips
        self.payslip = Payslip.objects.create(
            payroll_record=self.record,
            payslip_number="PS-202601-EMP001",
            status=Payslip.Status.GENERATED,
        )
        self.payslip2 = Payslip.objects.create(
            payroll_record=self.record2,
            payslip_number="PS-202601-EMP002",
            status=Payslip.Status.GENERATED,
        )


def _get_results(response):
    """Extract results from paginated or non-paginated response."""
    if isinstance(response.data, dict) and "results" in response.data:
        return response.data["results"]
    return response.data


class SalaryComponentAPITests(PayrollAPITestBase):
    def test_admin_can_list(self):
        self.client.force_authenticate(self.admin)
        SalaryComponent.objects.create(
            name="HRA", component_type=SalaryComponent.ComponentType.ALLOWANCE, amount=Decimal("5000.00")
        )
        response = self.client.get("/api/payroll/components/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 1)

    def test_hr_can_list(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get("/api/payroll/components/")
        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_list(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get("/api/payroll/components/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 0)  # filtered to none

    def test_admin_can_create(self):
        self.client.force_authenticate(self.admin)
        data = {
            "name": "HRA",
            "component_type": "ALLOWANCE",
            "amount": "5000.00",
        }
        response = self.client.post("/api/payroll/components/", data)
        self.assertEqual(response.status_code, 201)

    def test_employee_cannot_create(self):
        self.client.force_authenticate(self.employee_user)
        data = {
            "name": "HRA",
            "component_type": "ALLOWANCE",
            "amount": "5000.00",
        }
        response = self.client.post("/api/payroll/components/", data)
        self.assertEqual(response.status_code, 403)


class PayrollPeriodAPITests(PayrollAPITestBase):
    def test_admin_can_list(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/payroll/periods/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 1)

    def test_hr_can_list(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get("/api/payroll/periods/")
        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_list(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get("/api/payroll/periods/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 0)

    def test_admin_can_create(self):
        self.client.force_authenticate(self.admin)
        data = {
            "name": "February 2026",
            "start_date": "2026-02-01",
            "end_date": "2026-02-28",
        }
        response = self.client.post("/api/payroll/periods/", data)
        self.assertEqual(response.status_code, 201)


class PayrollRecordAPITests(PayrollAPITestBase):
    def test_admin_can_list_all(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/payroll/records/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 2)

    def test_hr_can_list_all(self):
        self.client.force_authenticate(self.hr)
        response = self.client.get("/api/payroll/records/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 2)

    def test_employee_can_list_own_only(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get("/api/payroll/records/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 1)
        self.assertEqual(_get_results(response)[0]["employee_id"], "EMP001")

    def test_admin_can_create(self):
        self.client.force_authenticate(self.admin)
        period = PayrollPeriod.objects.create(
            name="February 2026",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
        )
        data = {
            "employee": self.employee2.pk,
            "payroll_period": period.pk,
            "basic_salary": "60000.00",
            "total_allowances": "6000.00",
            "total_deductions": "4000.00",
        }
        response = self.client.post("/api/payroll/records/", data)
        self.assertEqual(response.status_code, 201)

    def test_employee_cannot_create(self):
        self.client.force_authenticate(self.employee_user)
        data = {
            "employee": self.employee.pk,
            "payroll_period": self.period.pk,
            "basic_salary": "50000.00",
        }
        response = self.client.post("/api/payroll/records/", data)
        self.assertEqual(response.status_code, 403)

    def test_admin_can_retrieve_any(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/payroll/records/{self.record2.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_employee_can_retrieve_own(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get(f"/api/payroll/records/{self.record.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_retrieve_other(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get(f"/api/payroll/records/{self.record2.pk}/")
        self.assertEqual(response.status_code, 404)  # filtered out

    def test_filter_by_period(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(f"/api/payroll/records/?period={self.period.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 2)


class PayslipAPITests(PayrollAPITestBase):
    def test_admin_can_list_all(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/payroll/payslips/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 2)

    def test_employee_can_list_own_only(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get("/api/payroll/payslips/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 1)
        self.assertEqual(_get_results(response)[0]["employee_id"], "EMP001")

    def test_employee_can_retrieve_own(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip.pk}/")
        self.assertEqual(response.status_code, 200)

    def test_employee_cannot_retrieve_other(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip2.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_payslip_download_own(self):
        self.client.force_authenticate(self.employee_user)
        # Generate PDF for the payslip first
        from apps.payroll.pdf_services import generate_payslip_pdf
        generate_payslip_pdf(self.record)
        self.payslip.refresh_from_db()

        response = self.client.get(f"/api/payroll/payslips/{self.payslip.pk}/download/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')

    def test_payslip_download_other_forbidden(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip2.pk}/download/")
        self.assertEqual(response.status_code, 403)

    def test_generate_payslip_admin(self):
        self.client.force_authenticate(self.admin)
        period = PayrollPeriod.objects.create(
            name="February 2026",
            start_date=date(2026, 2, 1),
            end_date=date(2026, 2, 28),
        )
        record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=period,
            basic_salary=Decimal("50000.00"),
        )
        response = self.client.post(f"/api/payroll/records/{record.pk}/generate-payslip/")
        self.assertEqual(response.status_code, 201)

    def test_generate_payslip_employee_forbidden(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.post(f"/api/payroll/records/{self.record.pk}/generate-payslip/")
        self.assertEqual(response.status_code, 403)


class NotificationLogAPITests(PayrollAPITestBase):
    def setUp(self):
        super().setUp()
        NotificationLog.objects.create(
            recipient="employee@test.com",
            notification_type=NotificationLog.NotificationType.LEAVE_DECISION,
            subject="Leave Approved",
            status=NotificationLog.Status.SENT,
        )
        NotificationLog.objects.create(
            recipient="employee2@test.com",
            notification_type=NotificationLog.NotificationType.PAYSLIP_READY,
            subject="Payslip Ready",
            status=NotificationLog.Status.SENT,
        )

    def test_admin_can_list_all(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get("/api/payroll/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 2)

    def test_employee_can_list_own_only(self):
        self.client.force_authenticate(self.employee_user)
        response = self.client.get("/api/payroll/notifications/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(_get_results(response)), 1)
        self.assertEqual(_get_results(response)[0]["recipient"], "employee@test.com")


class PayrollAuditSignalTests(PayrollAPITestBase):
    """Test that audit signals are triggered for payroll models."""

    def test_salary_component_audit_on_create(self):
        self.client.force_authenticate(self.admin)
        data = {
            "name": "Test Allowance",
            "component_type": "ALLOWANCE",
            "amount": "1000.00",
        }
        response = self.client.post("/api/payroll/components/", data)
        self.assertEqual(response.status_code, 201)

        # Check audit event was created
        from apps.accounts.models import AuditEvent
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(SalaryComponent)
        events = AuditEvent.objects.filter(
            content_type=ct, object_id=response.data["id"], action="CREATE"
        )
        self.assertEqual(events.count(), 1)

    def test_payroll_record_audit_on_create(self):
        self.client.force_authenticate(self.admin)
        period = PayrollPeriod.objects.create(
            name="March 2026",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        data = {
            "employee": self.employee.pk,
            "payroll_period": period.pk,
            "basic_salary": "50000.00",
            "total_allowances": "5000.00",
            "total_deductions": "3000.00",
        }
        response = self.client.post("/api/payroll/records/", data)
        self.assertEqual(response.status_code, 201)

        from apps.accounts.models import AuditEvent
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(PayrollRecord)
        events = AuditEvent.objects.filter(
            content_type=ct, object_id=response.data["id"], action="CREATE"
        )
        self.assertEqual(events.count(), 1)

    def test_payslip_audit_on_create(self):
        self.client.force_authenticate(self.admin)
        period = PayrollPeriod.objects.create(
            name="March 2026",
            start_date=date(2026, 3, 1),
            end_date=date(2026, 3, 31),
        )
        record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=period,
            basic_salary=Decimal("50000.00"),
        )
        response = self.client.post(f"/api/payroll/records/{record.pk}/generate-payslip/")
        self.assertEqual(response.status_code, 201)

        from apps.accounts.models import AuditEvent
        from django.contrib.contenttypes.models import ContentType

        ct = ContentType.objects.get_for_model(Payslip)
        events = AuditEvent.objects.filter(
            content_type=ct, object_id=response.data["id"], action="CREATE"
        )
        self.assertEqual(events.count(), 1)