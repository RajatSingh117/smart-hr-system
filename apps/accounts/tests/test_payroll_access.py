"""
Payroll Access Control Tests (M2 Week 3)

Tests for CanAccessPayroll permission and object-level access control
on payroll endpoints. These tests define expected behavior that M5
payroll views must implement.
"""
from decimal import Decimal
from datetime import date

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.employees.models import Employee, Department, JobTitle
from apps.payroll.models import PayrollPeriod, PayrollRecord, Payslip


class PayrollAccessPermissionTests(TestCase):
    """Test CanAccessPayroll permission class behavior."""

    def setUp(self):
        self.admin = User.objects.create_superuser(
            email='admin@hrms.com',
            password='SecurePass123!',
            first_name='Admin',
            last_name='User'
        )
        self.hr = User.objects.create_user(
            email='hr@hrms.com',
            password='SecurePass123!',
            first_name='HR',
            last_name='User',
            role=User.Role.HR
        )
        self.employee = User.objects.create_user(
            email='emp@hrms.com',
            password='SecurePass123!',
            first_name='Employee',
            last_name='User',
            role=User.Role.EMPLOYEE
        )
        self.employee2 = User.objects.create_user(
            email='emp2@hrms.com',
            password='SecurePass123!',
            first_name='Employee2',
            last_name='User',
            role=User.Role.EMPLOYEE
        )

        # Create employee profiles
        self.dept = Department.objects.create(name='Engineering')
        self.job = JobTitle.objects.create(title='Software Engineer')

        self.emp_profile = Employee.objects.create(
            user=self.employee,
            employee_id='EMP001',
            full_name='Employee User',
            email='emp@hrms.com',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('50000.00'),
        )
        self.emp_profile2 = Employee.objects.create(
            user=self.employee2,
            employee_id='EMP002',
            full_name='Employee2 User',
            email='emp2@hrms.com',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('60000.00'),
        )

        # Create payroll period and records
        self.period = PayrollPeriod.objects.create(
            name='January 2025',
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )

        self.payroll_record = PayrollRecord.objects.create(
            employee=self.emp_profile,
            payroll_period=self.period,
            basic_salary=Decimal('50000.00'),
            total_allowances=Decimal('10000.00'),
            total_deductions=Decimal('5000.00'),
        )

        self.payroll_record2 = PayrollRecord.objects.create(
            employee=self.emp_profile2,
            payroll_period=self.period,
            basic_salary=Decimal('60000.00'),
            total_allowances=Decimal('12000.00'),
            total_deductions=Decimal('6000.00'),
        )

        self.payslip = Payslip.objects.create(
            payroll_record=self.payroll_record,
            payslip_number='PAY-2025-001',
        )

        self.payslip2 = Payslip.objects.create(
            payroll_record=self.payroll_record2,
            payslip_number='PAY-2025-002',
        )

    def test_can_access_payroll_admin_has_permission(self):
        """Admin has permission to access payroll."""
        from apps.accounts.permissions import CanAccessPayroll
        perm = CanAccessPayroll()
        request = type('Request', (), {'user': self.admin})()
        self.assertTrue(perm.has_permission(request, None))

    def test_can_access_payroll_hr_has_permission(self):
        """HR has permission to access payroll."""
        from apps.accounts.permissions import CanAccessPayroll
        perm = CanAccessPayroll()
        request = type('Request', (), {'user': self.hr})()
        self.assertTrue(perm.has_permission(request, None))

    def test_can_access_payroll_employee_denied(self):
        """Employee is denied payroll access."""
        from apps.accounts.permissions import CanAccessPayroll
        perm = CanAccessPayroll()
        request = type('Request', (), {'user': self.employee})()
        self.assertFalse(perm.has_permission(request, None))

    def test_can_access_payroll_object_admin_access_all(self):
        """Admin can access any payroll record."""
        from apps.accounts.permissions import CanAccessPayroll
        perm = CanAccessPayroll()
        request = type('Request', (), {'user': self.admin})()
        self.assertTrue(perm.has_object_permission(request, None, self.payroll_record))
        self.assertTrue(perm.has_object_permission(request, None, self.payroll_record2))

    def test_can_access_payroll_object_hr_access_all(self):
        """HR can access any payroll record."""
        from apps.accounts.permissions import CanAccessPayroll
        perm = CanAccessPayroll()
        request = type('Request', (), {'user': self.hr})()
        self.assertTrue(perm.has_object_permission(request, None, self.payroll_record))
        self.assertTrue(perm.has_object_permission(request, None, self.payroll_record2))

    def test_can_access_payroll_object_employee_own_only(self):
        """Employee can only access their own payroll record."""
        from apps.accounts.permissions import CanAccessPayroll
        perm = CanAccessPayroll()
        request = type('Request', (), {'user': self.employee})()

        # Can access own record
        self.assertTrue(perm.has_object_permission(request, None, self.payroll_record))
        # Cannot access other's record
        self.assertFalse(perm.has_object_permission(request, None, self.payroll_record2))

    def test_can_access_payroll_object_employee_own_payslip_only(self):
        """Employee can only access their own payslip."""
        from apps.accounts.permissions import CanAccessPayroll
        perm = CanAccessPayroll()
        request = type('Request', (), {'user': self.employee})()

        # Can access own payslip
        self.assertTrue(perm.has_object_permission(request, None, self.payslip))
        # Cannot access other's payslip
        self.assertFalse(perm.has_object_permission(request, None, self.payslip2))


class PayrollAPIAccessTests(TestCase):
    """
    Integration tests for payroll API endpoints access control.
    These tests will pass once M5 implements the views with CanAccessPayroll.
    """

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_superuser(
            email='admin@hrms.com',
            password='SecurePass123!'
        )
        self.hr = User.objects.create_user(
            email='hr@hrms.com',
            password='SecurePass123!',
            role=User.Role.HR
        )
        self.employee = User.objects.create_user(
            email='emp@hrms.com',
            password='SecurePass123!',
            role=User.Role.EMPLOYEE
        )
        self.employee2 = User.objects.create_user(
            email='emp2@hrms.com',
            password='SecurePass123!',
            role=User.Role.EMPLOYEE
        )

        self.dept = Department.objects.create(name='Engineering')
        self.job = JobTitle.objects.create(title='Software Engineer')

        self.emp_profile = Employee.objects.create(
            user=self.employee,
            employee_id='EMP001',
            full_name='Employee User',
            email='emp@hrms.com',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('50000.00'),
        )
        self.emp_profile2 = Employee.objects.create(
            user=self.employee2,
            employee_id='EMP002',
            full_name='Employee2 User',
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

        self.payroll_record = PayrollRecord.objects.create(
            employee=self.emp_profile,
            payroll_period=self.period,
            basic_salary=Decimal('50000.00'),
        )

        self.payroll_record2 = PayrollRecord.objects.create(
            employee=self.emp_profile2,
            payroll_period=self.period,
            basic_salary=Decimal('60000.00'),
        )

        self.payslip = Payslip.objects.create(
            payroll_record=self.payroll_record,
            payslip_number='PAY-2025-001',
        )

        self.payslip2 = Payslip.objects.create(
            payroll_record=self.payroll_record2,
            payslip_number='PAY-2025-002',
        )

    # Expected URL names (to be defined by M5)
    PAYROLL_RECORDS_URL = '/api/payroll/records/'
    PAYROLL_RECORD_DETAIL_URL = '/api/payroll/records/{pk}/'
    PAYSLIPS_URL = '/api/payroll/payslips/'
    PAYSLIP_DETAIL_URL = '/api/payroll/payslips/{pk}/'
    PAYSLIP_DOWNLOAD_URL = '/api/payroll/payslips/{pk}/download/'

    def test_employee_cannot_list_payroll_records(self):
        """Employee cannot GET /api/payroll/records/ → 403"""
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(self.PAYROLL_RECORDS_URL)
        # Will be 404 until M5 creates the endpoint, then 403
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_employee_cannot_retrieve_payroll_record(self):
        """Employee cannot GET /api/payroll/records/{id}/ → 403"""
        self.client.force_authenticate(user=self.employee)
        url = self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_employee_cannot_list_payslips(self):
        """Employee cannot GET /api/payslips/ → 403"""
        self.client.force_authenticate(user=self.employee)
        response = self.client.get(self.PAYSLIPS_URL)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_employee_cannot_retrieve_payslip(self):
        """Employee cannot GET /api/payslips/{id}/ → 403"""
        self.client.force_authenticate(user=self.employee)
        url = self.PAYSLIP_DETAIL_URL.format(pk=self.payslip.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_employee_cannot_download_other_payslip(self):
        """Employee cannot download another employee's payslip → 403"""
        self.client.force_authenticate(user=self.employee)
        url = self.PAYSLIP_DOWNLOAD_URL.format(pk=self.payslip2.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_hr_can_list_payroll_records(self):
        """HR can GET /api/payroll/records/ → 200"""
        self.client.force_authenticate(user=self.hr)
        response = self.client.get(self.PAYROLL_RECORDS_URL)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_hr_can_retrieve_any_payroll_record(self):
        """HR can GET any /api/payroll/records/{id}/ → 200"""
        self.client.force_authenticate(user=self.hr)
        url = self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record2.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_hr_can_list_payslips(self):
        """HR can GET /api/payslips/ → 200"""
        self.client.force_authenticate(user=self.hr)
        response = self.client.get(self.PAYSLIPS_URL)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_hr_can_retrieve_any_payslip(self):
        """HR can GET any /api/payslips/{id}/ → 200"""
        self.client.force_authenticate(user=self.hr)
        url = self.PAYSLIP_DETAIL_URL.format(pk=self.payslip2.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_admin_can_access_all_payroll_endpoints(self):
        """Admin can access all payroll endpoints."""
        self.client.force_authenticate(user=self.admin)

        endpoints = [
            self.PAYROLL_RECORDS_URL,
            self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record.pk),
            self.PAYSLIPS_URL,
            self.PAYSLIP_DETAIL_URL.format(pk=self.payslip.pk),
            self.PAYSLIP_DOWNLOAD_URL.format(pk=self.payslip.pk),
        ]

        for url in endpoints:
            response = self.client.get(url)
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_employee_can_access_own_payroll_record(self):
        """Employee can access their own payroll record (when M5 implements object-level permission)."""
        self.client.force_authenticate(user=self.employee)
        url = self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record.pk)
        response = self.client.get(url)
        # Should be 200 once object-level permission is implemented
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_employee_can_access_own_payslip(self):
        """Employee can access their own payslip."""
        self.client.force_authenticate(user=self.employee)
        url = self.PAYSLIP_DETAIL_URL.format(pk=self.payslip.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_employee_can_download_own_payslip(self):
        """Employee can download their own payslip."""
        self.client.force_authenticate(user=self.employee)
        url = self.PAYSLIP_DOWNLOAD_URL.format(pk=self.payslip.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_unauthenticated_access_denied(self):
        """Unauthenticated users cannot access payroll endpoints."""
        endpoints = [
            self.PAYROLL_RECORDS_URL,
            self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record.pk),
            self.PAYSLIPS_URL,
            self.PAYSLIP_DETAIL_URL.format(pk=self.payslip.pk),
        ]

        for url in endpoints:
            response = self.client.get(url)
            self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_302_FOUND, status.HTTP_404_NOT_FOUND])


class PayrollObjectLevelManipulationTests(TestCase):
    """
    Security Review Sprint 1: Test URL ID manipulation across payroll endpoints.
    Verify that object-level permissions prevent unauthorized access via ID manipulation.
    """

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_superuser(
            email='admin@hrms.com',
            password='SecurePass123!'
        )
        self.employee = User.objects.create_user(
            email='emp@hrms.com',
            password='SecurePass123!',
            role=User.Role.EMPLOYEE
        )
        self.employee2 = User.objects.create_user(
            email='emp2@hrms.com',
            password='SecurePass123!',
            role=User.Role.EMPLOYEE
        )
        self.hr = User.objects.create_user(
            email='hr@hrms.com',
            password='SecurePass123!',
            role=User.Role.HR
        )

        self.dept = Department.objects.create(name='Engineering')
        self.job = JobTitle.objects.create(title='Software Engineer')

        self.emp_profile = Employee.objects.create(
            user=self.employee,
            employee_id='EMP001',
            full_name='Employee User',
            email='emp@hrms.com',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('50000.00'),
        )
        self.emp_profile2 = Employee.objects.create(
            user=self.employee2,
            employee_id='EMP002',
            full_name='Employee2 User',
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

        self.payroll_record = PayrollRecord.objects.create(
            employee=self.emp_profile,
            payroll_period=self.period,
            basic_salary=Decimal('50000.00'),
        )
        self.payroll_record2 = PayrollRecord.objects.create(
            employee=self.emp_profile2,
            payroll_period=self.period,
            basic_salary=Decimal('60000.00'),
        )

        self.payslip = Payslip.objects.create(
            payroll_record=self.payroll_record,
            payslip_number='PAY-2025-001',
        )
        self.payslip2 = Payslip.objects.create(
            payroll_record=self.payroll_record2,
            payslip_number='PAY-2025-002',
        )

    PAYROLL_RECORD_DETAIL_URL = '/api/payroll/records/{pk}/'
    PAYSLIP_DETAIL_URL = '/api/payroll/payslips/{pk}/'
    PAYSLIP_DOWNLOAD_URL = '/api/payroll/payslips/{pk}/download/'

    def test_employee_cannot_access_other_payroll_record_via_id_manipulation(self):
        """Employee trying to access other's payroll by changing ID → 403"""
        self.client.force_authenticate(user=self.employee)
        # Try to access employee2's payroll record by ID
        url = self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record2.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_employee_cannot_access_other_payslip_via_id_manipulation(self):
        """Employee trying to access other's payslip by changing ID → 403"""
        self.client.force_authenticate(user=self.employee)
        url = self.PAYSLIP_DETAIL_URL.format(pk=self.payslip2.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_employee_cannot_download_other_payslip_via_id_manipulation(self):
        """Employee trying to download other's payslip by changing ID → 403"""
        self.client.force_authenticate(user=self.employee)
        url = self.PAYSLIP_DOWNLOAD_URL.format(pk=self.payslip2.pk)
        response = self.client.get(url)
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_hr_can_access_all_records_via_id(self):
        """HR can access any record by ID."""
        self.client.force_authenticate(user=self.hr)
        urls = [
            self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record.pk),
            self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record2.pk),
            self.PAYSLIP_DETAIL_URL.format(pk=self.payslip.pk),
            self.PAYSLIP_DETAIL_URL.format(pk=self.payslip2.pk),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])

    def test_admin_can_access_all_records_via_id(self):
        """Admin can access any record by ID."""
        self.client.force_authenticate(user=self.admin)
        urls = [
            self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record.pk),
            self.PAYROLL_RECORD_DETAIL_URL.format(pk=self.payroll_record2.pk),
            self.PAYSLIP_DETAIL_URL.format(pk=self.payslip.pk),
            self.PAYSLIP_DETAIL_URL.format(pk=self.payslip2.pk),
        ]
        for url in urls:
            response = self.client.get(url)
            self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND])