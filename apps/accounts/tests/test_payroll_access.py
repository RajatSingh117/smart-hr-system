"""
Payroll Access Control Tests (M2 Week 3)

Tests for CanAccessPayroll permission and object-level access control
on payroll endpoints.
"""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.accounts.permissions import CanAccessPayroll
from apps.employees.models import Employee, Department, JobTitle
from apps.payroll.models import PayrollPeriod, PayrollRecord, Payslip


class PayrollTestDataMixin:
    """Common test data shared by all payroll access tests."""

    def create_test_data(self):
        self.admin = User.objects.create_superuser(
            email="admin@hrms.com",
            password="SecurePass123!",
            first_name="Admin",
            last_name="User",
        )

        self.hr = User.objects.create_user(
            email="hr@hrms.com",
            password="SecurePass123!",
            first_name="HR",
            last_name="User",
            role=User.Role.HR,
        )

        self.employee = User.objects.create_user(
            email="emp@hrms.com",
            password="SecurePass123!",
            first_name="Employee",
            last_name="User",
            role=User.Role.EMPLOYEE,
        )

        self.employee2 = User.objects.create_user(
            email="emp2@hrms.com",
            password="SecurePass123!",
            first_name="Employee2",
            last_name="User",
            role=User.Role.EMPLOYEE,
        )

        self.dept = Department.objects.create(
            name="Engineering"
        )

        self.job = JobTitle.objects.create(
            title="Software Engineer"
        )

        self.emp_profile = Employee.objects.create(
            user=self.employee,
            employee_id="EMP001",
            full_name="Employee User",
            email="emp@hrms.com",
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal("50000.00"),
        )

        self.emp_profile2 = Employee.objects.create(
            user=self.employee2,
            employee_id="EMP002",
            full_name="Employee2 User",
            email="emp2@hrms.com",
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal("60000.00"),
        )

        self.period = PayrollPeriod.objects.create(
            name="January 2025",
            start_date=date(2025, 1, 1),
            end_date=date(2025, 1, 31),
        )

        self.payroll_record = PayrollRecord.objects.create(
            employee=self.emp_profile,
            payroll_period=self.period,
            basic_salary=Decimal("50000.00"),
        )

        self.payroll_record2 = PayrollRecord.objects.create(
            employee=self.emp_profile2,
            payroll_period=self.period,
            basic_salary=Decimal("60000.00"),
        )

        self.payslip = Payslip.objects.create(
            payroll_record=self.payroll_record,
            payslip_number="PAY-2025-001",
        )

        self.payslip2 = Payslip.objects.create(
            payroll_record=self.payroll_record2,
            payslip_number="PAY-2025-002",
        )


class PayrollAccessPermissionTests(
    PayrollTestDataMixin,
    TestCase,
):
    """Test CanAccessPayroll permission class."""

    def setUp(self):
        self.create_test_data()

    def test_admin_has_permission(self):
        permission = CanAccessPayroll()
        request = type("Request", (), {"user": self.admin})()

        self.assertTrue(
            permission.has_permission(request, None)
        )

    def test_hr_has_permission(self):
        permission = CanAccessPayroll()
        request = type("Request", (), {"user": self.hr})()

        self.assertTrue(
            permission.has_permission(request, None)
        )

    def test_employee_denied_general_permission(self):
        permission = CanAccessPayroll()
        request = type("Request", (), {"user": self.employee})()

        self.assertFalse(
            permission.has_permission(request, None)
        )

    def test_admin_can_access_all_payroll_records(self):
        permission = CanAccessPayroll()
        request = type("Request", (), {"user": self.admin})()

        self.assertTrue(
            permission.has_object_permission(
                request, None, self.payroll_record
            )
        )

        self.assertTrue(
            permission.has_object_permission(
                request, None, self.payroll_record2
            )
        )

    def test_hr_can_access_all_payroll_records(self):
        permission = CanAccessPayroll()
        request = type("Request", (), {"user": self.hr})()

        self.assertTrue(
            permission.has_object_permission(
                request, None, self.payroll_record
            )
        )

        self.assertTrue(
            permission.has_object_permission(
                request, None, self.payroll_record2
            )
        )

    def test_employee_can_access_only_own_payroll_record(self):
        permission = CanAccessPayroll()
        request = type("Request", (), {"user": self.employee})()

        self.assertTrue(
            permission.has_object_permission(
                request, None, self.payroll_record
            )
        )

        self.assertFalse(
            permission.has_object_permission(
                request, None, self.payroll_record2
            )
        )

    def test_employee_can_access_only_own_payslip(self):
        permission = CanAccessPayroll()
        request = type("Request", (), {"user": self.employee})()

        self.assertTrue(
            permission.has_object_permission(
                request, None, self.payslip
            )
        )

        self.assertFalse(
            permission.has_object_permission(
                request, None, self.payslip2
            )
        )


class PayrollAPIAccessTests(
    PayrollTestDataMixin,
    TestCase,
):
    """Integration tests for payroll API access control."""

    PAYROLL_RECORDS_URL = "/api/payroll/records/"
    PAYROLL_RECORD_DETAIL_URL = "/api/payroll/records/{pk}/"

    PAYSLIPS_URL = "/api/payroll/payslips/"
    PAYSLIP_DETAIL_URL = "/api/payroll/payslips/{pk}/"

    PAYSLIP_DOWNLOAD_URL = (
        "/api/payroll/payslips/{pk}/download/"
    )

    def setUp(self):
        self.client = APIClient()
        self.create_test_data()

    def test_employee_cannot_list_payroll_records(self):
        self.client.force_authenticate(
            user=self.employee
        )

        response = self.client.get(
            self.PAYROLL_RECORDS_URL
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_employee_cannot_retrieve_other_payroll_record(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYROLL_RECORD_DETAIL_URL.format(
            pk=self.payroll_record2.pk
        )

        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_employee_cannot_list_payslips(self):
        self.client.force_authenticate(
            user=self.employee
        )

        response = self.client.get(
            self.PAYSLIPS_URL
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_employee_cannot_retrieve_other_payslip(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYSLIP_DETAIL_URL.format(
            pk=self.payslip2.pk
        )

        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_employee_cannot_download_other_payslip(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYSLIP_DOWNLOAD_URL.format(
            pk=self.payslip2.pk
        )

        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_hr_can_list_payroll_records(self):
        self.client.force_authenticate(
            user=self.hr
        )

        response = self.client.get(
            self.PAYROLL_RECORDS_URL
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_hr_can_retrieve_any_payroll_record(self):
        self.client.force_authenticate(
            user=self.hr
        )

        url = self.PAYROLL_RECORD_DETAIL_URL.format(
            pk=self.payroll_record2.pk
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_hr_can_list_payslips(self):
        self.client.force_authenticate(
            user=self.hr
        )

        response = self.client.get(
            self.PAYSLIPS_URL
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_hr_can_retrieve_any_payslip(self):
        self.client.force_authenticate(
            user=self.hr
        )

        url = self.PAYSLIP_DETAIL_URL.format(
            pk=self.payslip2.pk
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_admin_can_access_all_payroll_endpoints(self):
        self.client.force_authenticate(
            user=self.admin
        )

        endpoints = [
            self.PAYROLL_RECORDS_URL,
            self.PAYROLL_RECORD_DETAIL_URL.format(
                pk=self.payroll_record.pk
            ),
            self.PAYSLIPS_URL,
            self.PAYSLIP_DETAIL_URL.format(
                pk=self.payslip.pk
            ),
        ]

        for url in endpoints:
            response = self.client.get(url)

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
                msg=f"Unexpected response for {url}",
            )

        # The test payslip has no generated PDF file.
        # A 404 is therefore expected for the download.
        download_url = self.PAYSLIP_DOWNLOAD_URL.format(
            pk=self.payslip.pk
        )

        response = self.client.get(download_url)

        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_employee_can_access_own_payroll_record(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYROLL_RECORD_DETAIL_URL.format(
            pk=self.payroll_record.pk
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_employee_can_access_own_payslip(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYSLIP_DETAIL_URL.format(
            pk=self.payslip.pk
        )

        response = self.client.get(url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK,
        )

    def test_employee_can_download_own_payslip(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYSLIP_DOWNLOAD_URL.format(
            pk=self.payslip.pk
        )

        response = self.client.get(url)

        # No PDF has been generated for this test payslip.
        self.assertEqual(
            response.status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_unauthenticated_access_denied(self):
        endpoints = [
            self.PAYROLL_RECORDS_URL,
            self.PAYROLL_RECORD_DETAIL_URL.format(
                pk=self.payroll_record.pk
            ),
            self.PAYSLIPS_URL,
            self.PAYSLIP_DETAIL_URL.format(
                pk=self.payslip.pk
            ),
        ]

        for url in endpoints:
            response = self.client.get(url)

            self.assertIn(
                response.status_code,
                [
                    status.HTTP_401_UNAUTHORIZED,
                    status.HTTP_403_FORBIDDEN,
                ],
                msg=f"Unauthenticated access was not denied for {url}",
            )


class PayrollObjectLevelManipulationTests(
    PayrollTestDataMixin,
    TestCase,
):
    """Test protection against payroll URL ID manipulation."""

    PAYROLL_RECORD_DETAIL_URL = (
        "/api/payroll/records/{pk}/"
    )

    PAYSLIP_DETAIL_URL = (
        "/api/payroll/payslips/{pk}/"
    )

    PAYSLIP_DOWNLOAD_URL = (
        "/api/payroll/payslips/{pk}/download/"
    )

    def setUp(self):
        self.client = APIClient()
        self.create_test_data()

    def test_employee_cannot_access_other_record_by_changing_id(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYROLL_RECORD_DETAIL_URL.format(
            pk=self.payroll_record2.pk
        )

        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_employee_cannot_access_other_payslip_by_changing_id(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYSLIP_DETAIL_URL.format(
            pk=self.payslip2.pk
        )

        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_employee_cannot_download_other_payslip_by_changing_id(self):
        self.client.force_authenticate(
            user=self.employee
        )

        url = self.PAYSLIP_DOWNLOAD_URL.format(
            pk=self.payslip2.pk
        )

        response = self.client.get(url)

        self.assertIn(
            response.status_code,
            [
                status.HTTP_403_FORBIDDEN,
                status.HTTP_404_NOT_FOUND,
            ],
        )

    def test_hr_can_access_all_records_by_id(self):
        self.client.force_authenticate(
            user=self.hr
        )

        urls = [
            self.PAYROLL_RECORD_DETAIL_URL.format(
                pk=self.payroll_record.pk
            ),
            self.PAYROLL_RECORD_DETAIL_URL.format(
                pk=self.payroll_record2.pk
            ),
            self.PAYSLIP_DETAIL_URL.format(
                pk=self.payslip.pk
            ),
            self.PAYSLIP_DETAIL_URL.format(
                pk=self.payslip2.pk
            ),
        ]

        for url in urls:
            response = self.client.get(url)

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
            )

    def test_admin_can_access_all_records_by_id(self):
        self.client.force_authenticate(
            user=self.admin
        )

        urls = [
            self.PAYROLL_RECORD_DETAIL_URL.format(
                pk=self.payroll_record.pk
            ),
            self.PAYROLL_RECORD_DETAIL_URL.format(
                pk=self.payroll_record2.pk
            ),
            self.PAYSLIP_DETAIL_URL.format(
                pk=self.payslip.pk
            ),
            self.PAYSLIP_DETAIL_URL.format(
                pk=self.payslip2.pk
            ),
        ]

        for url in urls:
            response = self.client.get(url)

            self.assertEqual(
                response.status_code,
                status.HTTP_200_OK,
            )
