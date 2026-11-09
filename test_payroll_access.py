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
from django.core.files.uploadedfile import SimpleUploadedFile


class PayrollAccessPermissionTests(TestCase):
    """Test CanAccessPayroll permission class behavior."""

    def setUp(self):
        self.admin = User.objects.create_user(
            email="admin@hrms.com", password="SecurePass123!", role=User.Role.ADMIN
        )
        self.hr = User.objects.create_user(
            email="hr@hrms.com", password="SecurePass123!", role=User.Role.HR
        )
        self.employee = User.objects.create_user(
            email="emp@hrms.com", password="SecurePass123!", role=User.Role.EMPLOYEE
        )
        self.employee2 = User.objects.create_user(
            email="emp2@hrms.com", password="SecurePass123!", role=User.Role.EMPLOYEE
        )

        dept = Department.objects.create(name="Engineering")
        job = JobTitle.objects.create(title="Software Engineer")

        self.emp1 = Employee.objects.create(
            user=self.employee,
            employee_id="EMP001",
            full_name="Employee User",
            email="emp@hrms.com",
            department=dept,
            job_title=job,
            joining_date=date(2024, 1, 15),
            base_salary=Decimal("50000.00"),
        )
        self.emp2 = Employee.objects.create(
            user=self.employee2,
            employee_id="EMP002",
            full_name="Employee2 User",
            email="emp2@hrms.com",
            department=dept,
            job_title=job,
            joining_date=date(2024, 1, 15),
            base_salary=Decimal("50000.00"),
        )

        period = PayrollPeriod.objects.create(name="January 2025", start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        self.record1 = PayrollRecord.objects.create(
            employee=self.emp1, payroll_period=period, basic_salary=Decimal("50000.00"), total_allowances=Decimal("5000.00"), total_deductions=Decimal("3000.00")
        )
        self.record2 = PayrollRecord.objects.create(
            employee=self.emp2, payroll_period=period, basic_salary=Decimal("50000.00"), total_allowances=Decimal("5000.00"), total_deductions=Decimal("3000.00")
        )
        self.payslip1 = Payslip.objects.create(payroll_record=self.record1, payslip_number="PAY-2025-001")
        self.payslip2 = Payslip.objects.create(payroll_record=self.record2, payslip_number="PAY-2025-002")

    def test_can_access_payroll_admin_has_permission(self):
        """Admin has permission to access payroll."""
        from apps.accounts.permissions import CanAccessPayroll
        from rest_framework.request import Request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = Request(factory.get("/api/payroll/records/"))
        request.user = self.admin

        perm = CanAccessPayroll()
        self.assertTrue(perm.has_permission(request, None))

    def test_can_access_payroll_hr_has_permission(self):
        """HR has permission to access payroll."""
        from apps.accounts.permissions import CanAccessPayroll
        from rest_framework.request import Request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = Request(factory.get("/api/payroll/records/"))
        request.user = self.hr

        perm = CanAccessPayroll()
        self.assertTrue(perm.has_permission(request, None))

    def test_can_access_payroll_employee_allowed_at_view_level(self):
        """Employee is allowed at view level; object permission enforces ownership."""
        from apps.accounts.permissions import CanAccessPayroll
        from rest_framework.request import Request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = Request(factory.get("/api/payroll/records/"))
        request.user = self.employee

        perm = CanAccessPayroll()
        self.assertTrue(perm.has_permission(request, None))

    def test_can_access_payroll_object_admin_access_all(self):
        """Admin can access any payroll record."""
        from apps.accounts.permissions import CanAccessPayroll
        from rest_framework.request import Request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = Request(factory.get("/api/payroll/records/"))
        request.user = self.admin

        perm = CanAccessPayroll()
        self.assertTrue(perm.has_object_permission(request, None, self.record1))
        self.assertTrue(perm.has_object_permission(request, None, self.record2))
        self.assertTrue(perm.has_object_permission(request, None, self.payslip1))
        self.assertTrue(perm.has_object_permission(request, None, self.payslip2))

    def test_can_access_payroll_object_hr_access_all(self):
        """HR can access any payroll record."""
        from apps.accounts.permissions import CanAccessPayroll
        from rest_framework.request import Request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = Request(factory.get("/api/payroll/records/"))
        request.user = self.hr

        perm = CanAccessPayroll()
        self.assertTrue(perm.has_object_permission(request, None, self.record1))
        self.assertTrue(perm.has_object_permission(request, None, self.record2))
        self.assertTrue(perm.has_object_permission(request, None, self.payslip1))
        self.assertTrue(perm.has_object_permission(request, None, self.payslip2))

    def test_can_access_payroll_object_employee_own_only(self):
        """Employee can only access their own payroll record."""
        from apps.accounts.permissions import CanAccessPayroll
        from rest_framework.request import Request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = Request(factory.get("/api/payroll/records/"))
        request.user = self.employee

        perm = CanAccessPayroll()
        self.assertTrue(perm.has_object_permission(request, None, self.record1))
        self.assertFalse(perm.has_object_permission(request, None, self.record2))

    def test_can_access_payroll_object_employee_own_payslip_only(self):
        """Employee can only access their own payslip."""
        from apps.accounts.permissions import CanAccessPayroll
        from rest_framework.request import Request
        from django.test import RequestFactory

        factory = RequestFactory()
        request = Request(factory.get("/api/payroll/payslips/"))
        request.user = self.employee

        perm = CanAccessPayroll()
        self.assertTrue(perm.has_object_permission(request, None, self.payslip1))
        self.assertFalse(perm.has_object_permission(request, None, self.payslip2))


class PayrollAPIAccessTests(TestCase):
    """
    Integration tests for payroll API endpoints access control.
    These tests will pass once M5 implements the views with CanAccessPayroll.
    """

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@hrms.com", password="SecurePass123!", role=User.Role.ADMIN
        )
        self.hr = User.objects.create_user(
            email="hr@hrms.com", password="SecurePass123!", role=User.Role.HR
        )
        self.employee = User.objects.create_user(
            email="emp@hrms.com", password="SecurePass123!", role=User.Role.EMPLOYEE
        )
        self.employee2 = User.objects.create_user(
            email="emp2@hrms.com", password="SecurePass123!", role=User.Role.EMPLOYEE
        )

        dept = Department.objects.create(name="Engineering")
        job = JobTitle.objects.create(title="Software Engineer")

        self.emp1 = Employee.objects.create(
            user=self.employee,
            employee_id="EMP001",
            full_name="Employee User",
            email="emp@hrms.com",
            department=dept,
            job_title=job,
            joining_date=date(2024, 1, 15),
            base_salary=Decimal("50000.00"),
        )
        self.emp2 = Employee.objects.create(
            user=self.employee2,
            employee_id="EMP002",
            full_name="Employee2 User",
            email="emp2@hrms.com",
            department=dept,
            job_title=job,
            joining_date=date(2024, 1, 15),
            base_salary=Decimal("50000.00"),
        )

        period = PayrollPeriod.objects.create(name="January 2025", start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        self.record1 = PayrollRecord.objects.create(
            employee=self.emp1, payroll_period=period, basic_salary=Decimal("50000.00"), total_allowances=Decimal("5000.00"), total_deductions=Decimal("3000.00")
        )
        self.record2 = PayrollRecord.objects.create(
            employee=self.emp2, payroll_period=period, basic_salary=Decimal("50000.00"), total_allowances=Decimal("5000.00"), total_deductions=Decimal("3000.00")
        )
        self.payslip1 = Payslip.objects.create(payroll_record=self.record1, payslip_number="PAY-2025-001", status=Payslip.Status.GENERATED)
        self.payslip2 = Payslip.objects.create(payroll_record=self.record2, payslip_number="PAY-2025-002", status=Payslip.Status.GENERATED)

        # Attach a sample PDF to self.payslip1 for download testing
        sample_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n/Resources <<\n/Font <<\n/F1 5 0 R\n>>\n>>\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT /F1 12 Tf 100 700 Td (Test PDF) Tj ET\nendstream\nendobj\n5 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n0000000211 00000 n \n0000000301 00000 n \ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n380\n%%EOF"
        self.payslip1.pdf_file.save(
            f"{self.payslip1.payslip_number}.pdf",
            SimpleUploadedFile(
                f"{self.payslip1.payslip_number}.pdf",
                sample_pdf_content,
                content_type="application/pdf",
            ),
            save=True,
        )

    def test_employee_can_list_own_payroll_records_only(self):
        """Employee can list their own payroll records; cannot see others'."""
        self.client.force_authenticate(self.employee)
        response = self.client.get("/api/payroll/records/")
        # Employee should see only their own record
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["employee"], self.emp1.id)
        self.assertEqual(results[0]["employee"], self.emp1.id)

    def test_employee_can_list_own_payslips_only(self):
        """Employee can list their own payslips; cannot see others'."""
        self.client.force_authenticate(self.employee)
        response = self.client.get("/api/payroll/payslips/")
        # Employee should see only their own payslip
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get("results", response.data)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["payslip_number"], "PAY-2025-001")

    def test_employee_cannot_retrieve_other_payroll_record(self):
        """Employee cannot retrieve another employee's payroll record → 404 (filtered)."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/records/{self.record2.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_cannot_retrieve_other_payslip(self):
        """Employee cannot retrieve another employee's payslip → 404 (filtered)."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip2.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_cannot_download_other_payslip(self):
        """Employee cannot download another employee's payslip → 403."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip2.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_can_list_payroll_records(self):
        """HR can GET /api/payroll/records/ → 200."""
        self.client.force_authenticate(self.hr)
        response = self.client.get("/api/payroll/records/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get("results", response.data)
        self.assertEqual(len(results), 2)

    def test_hr_can_retrieve_any_payroll_record(self):
        """HR can GET any /api/payroll/records/{id}/ → 200."""
        self.client.force_authenticate(self.hr)
        response = self.client.get(f"/api/payroll/records/{self.record2.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_hr_can_list_payslips(self):
        """HR can GET /api/payslips/ → 200."""
        self.client.force_authenticate(self.hr)
        response = self.client.get("/api/payroll/payslips/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data if isinstance(response.data, list) else response.data.get("results", response.data)
        self.assertEqual(len(results), 2)

    def test_hr_can_retrieve_any_payslip(self):
        """HR can GET any /api/payslips/{id}/ → 200."""
        self.client.force_authenticate(self.hr)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip2.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_admin_can_access_all_payroll_endpoints(self):
        """Admin can access all payroll endpoints."""
        self.client.force_authenticate(self.admin)
        for url in [
            "/api/payroll/records/",
            f"/api/payroll/records/{self.record2.pk}/",
            "/api/payroll/payslips/",
            f"/api/payroll/payslips/{self.payslip2.pk}/",
            f"/api/payroll/payslips/{self.payslip1.pk}/download/",
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, f"Failed for {url}")

    def test_employee_can_access_own_payroll_record(self):
        """Employee can access their own payroll record → 200."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/records/{self.record1.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["employee"], self.emp1.id)

    def test_employee_can_access_own_payslip(self):
        """Employee can access their own payslip → 200."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip1.pk}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["payslip_number"], "PAY-2025-001")

    def test_employee_can_download_own_payslip(self):
        """Employee can download their own payslip → 200 with PDF content."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip1.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")
        # Verify PDF content
        content = b"".join(response.streaming_content)
        self.assertTrue(content.startswith(b"%PDF-"))
        self.assertIn(b"Test PDF", content)

    def test_unauthenticated_access_denied(self):
        """Unauthenticated users cannot access payroll endpoints."""
        for url in [
            "/api/payroll/records/",
            f"/api/payroll/records/{self.record1.pk}/",
            "/api/payroll/payslips/",
            f"/api/payroll/payslips/{self.payslip1.pk}/",
            f"/api/payroll/payslips/{self.payslip1.pk}/download/",
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED, f"Failed for {url}")


class PayrollObjectLevelManipulationTests(TestCase):
    """
    Security Review Sprint 1: Test URL ID manipulation across payroll endpoints.
    Verify that object-level permissions prevent unauthorized access via ID manipulation.
    """

    def setUp(self):
        self.client = APIClient()

        self.admin = User.objects.create_user(
            email="admin@hrms.com", password="SecurePass123!", role=User.Role.ADMIN
        )
        self.employee = User.objects.create_user(
            email="emp@hrms.com", password="SecurePass123!", role=User.Role.EMPLOYEE
        )
        self.employee2 = User.objects.create_user(
            email="emp2@hrms.com", password="SecurePass123!", role=User.Role.EMPLOYEE
        )
        self.hr = User.objects.create_user(
            email="hr@hrms.com", password="SecurePass123!", role=User.Role.HR
        )

        dept = Department.objects.create(name="Engineering")
        job = JobTitle.objects.create(title="Software Engineer")

        self.emp1 = Employee.objects.create(
            user=self.employee,
            employee_id="EMP001",
            full_name="Employee User",
            email="emp@hrms.com",
            department=dept,
            job_title=job,
            joining_date=date(2024, 1, 15),
            base_salary=Decimal("50000.00"),
        )
        self.emp2 = Employee.objects.create(
            user=self.employee2,
            employee_id="EMP002",
            full_name="Employee2 User",
            email="emp2@hrms.com",
            department=dept,
            job_title=job,
            joining_date=date(2024, 1, 15),
            base_salary=Decimal("50000.00"),
        )

        period = PayrollPeriod.objects.create(name="January 2025", start_date=date(2025, 1, 1), end_date=date(2025, 1, 31))
        self.record1 = PayrollRecord.objects.create(
            employee=self.emp1, payroll_period=period, basic_salary=Decimal("50000.00"), total_allowances=Decimal("5000.00"), total_deductions=Decimal("3000.00")
        )
        self.record2 = PayrollRecord.objects.create(
            employee=self.emp2, payroll_period=period, basic_salary=Decimal("50000.00"), total_allowances=Decimal("5000.00"), total_deductions=Decimal("3000.00")
        )
        self.payslip1 = Payslip.objects.create(payroll_record=self.record1, payslip_number="PAY-2025-001", status=Payslip.Status.GENERATED)
        self.payslip2 = Payslip.objects.create(payroll_record=self.record2, payslip_number="PAY-2025-002", status=Payslip.Status.GENERATED)

        # Attach sample PDF for download testing
        sample_pdf_content = b"%PDF-1.4\n1 0 obj\n<<\n/Type /Catalog\n/Pages 2 0 R\n>>\nendobj\n2 0 obj\n<<\n/Type /Pages\n/Kids [3 0 R]\n/Count 1\n>>\nendobj\n3 0 obj\n<<\n/Type /Page\n/Parent 2 0 R\n/MediaBox [0 0 612 792]\n/Contents 4 0 R\n/Resources <<\n/Font <<\n/F1 5 0 R\n>>\n>>\n>>\nendobj\n4 0 obj\n<<\n/Length 44\n>>\nstream\nBT /F1 12 Tf 100 700 Td (Test PDF) Tj ET\nendstream\nendobj\n5 0 obj\n<<\n/Type /Font\n/Subtype /Type1\n/BaseFont /Helvetica\n>>\nendobj\nxref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n0000000211 00000 n \n0000000301 00000 n \ntrailer\n<<\n/Size 6\n/Root 1 0 R\n>>\nstartxref\n380\n%%EOF"
        self.payslip1.pdf_file.save(
            f"{self.payslip1.payslip_number}.pdf",
            SimpleUploadedFile(
                f"{self.payslip1.payslip_number}.pdf",
                sample_pdf_content,
                content_type="application/pdf",
            ),
            save=True,
        )
        self.payslip2.pdf_file.save(
            f"{self.payslip2.payslip_number}.pdf",
            SimpleUploadedFile(
                f"{self.payslip2.payslip_number}.pdf",
                sample_pdf_content,
                content_type="application/pdf",
            ),
            save=True,
        )

    def test_employee_cannot_access_other_payroll_record_via_id_manipulation(self):
        """Employee trying to access other's payroll by changing ID → 404."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/records/{self.record2.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_cannot_access_other_payslip_via_id_manipulation(self):
        """Employee trying to access other's payslip by changing ID → 404."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip2.pk}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_employee_cannot_download_other_payslip_via_id_manipulation(self):
        """Employee trying to download other's payslip by changing ID → 403."""
        self.client.force_authenticate(self.employee)
        response = self.client.get(f"/api/payroll/payslips/{self.payslip2.pk}/download/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_hr_can_access_all_records_via_id(self):
        """HR can access any record by ID."""
        self.client.force_authenticate(self.hr)
        for url in [
            f"/api/payroll/records/{self.record1.pk}/",
            f"/api/payroll/records/{self.record2.pk}/",
            f"/api/payroll/payslips/{self.payslip1.pk}/",
            f"/api/payroll/payslips/{self.payslip2.pk}/",
            f"/api/payroll/payslips/{self.payslip1.pk}/download/",
            f"/api/payroll/payslips/{self.payslip2.pk}/download/",
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, f"Failed for {url}")

    def test_admin_can_access_all_records_via_id(self):
        """Admin can access any record by ID."""
        self.client.force_authenticate(self.admin)
        for url in [
            f"/api/payroll/records/{self.record1.pk}/",
            f"/api/payroll/records/{self.record2.pk}/",
            f"/api/payroll/payslips/{self.payslip1.pk}/",
            f"/api/payroll/payslips/{self.payslip2.pk}/",
            f"/api/payroll/payslips/{self.payslip1.pk}/download/",
            f"/api/payroll/payslips/{self.payslip2.pk}/download/",
        ]:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK, f"Failed for {url}")