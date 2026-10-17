from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.test import TestCase

from apps.employees.models import Department, JobTitle, Employee

User = get_user_model()


class DepartmentModelTests(TestCase):
    """Unit and relationship tests for the Department model."""

    def test_department_creation_and_str(self):
        dept = Department.objects.create(
            name='Engineering',
            description='Software engineering and infrastructure teams',
        )
        self.assertEqual(str(dept), 'Engineering')
        self.assertTrue(dept.is_active)
        self.assertIsNotNone(dept.created_at)
        self.assertIsNotNone(dept.updated_at)

    def test_department_name_uniqueness(self):
        Department.objects.create(name='Human Resources')
        with self.assertRaises(IntegrityError):
            Department.objects.create(name='Human Resources')

    def test_department_ordering(self):
        Department.objects.create(name='Sales')
        Department.objects.create(name='Accounting')
        Department.objects.create(name='Engineering')
        names = list(Department.objects.values_list('name', flat=True))
        self.assertEqual(names, ['Accounting', 'Engineering', 'Sales'])

    def test_department_head_assignment_and_set_null_on_delete(self):
        dept = Department.objects.create(name='Product')
        emp = Employee.objects.create(
            employee_id='EMP-H01',
            full_name='Head of Product',
            email='head.product@example.com',
            joining_date=date(2025, 1, 1),
            department=dept,
        )
        dept.department_head = emp
        dept.save()
        dept.refresh_from_db()
        self.assertEqual(dept.department_head, emp)
        self.assertIn(dept, emp.headed_departments.all())

        # When the head employee is deleted, department_head should become NULL (SET_NULL)
        emp.delete()
        dept.refresh_from_db()
        self.assertIsNone(dept.department_head)


class JobTitleModelTests(TestCase):
    """Unit and relationship tests for the JobTitle model."""

    def test_job_title_creation_and_str(self):
        title = JobTitle.objects.create(
            title='Staff Software Engineer',
            description='Technical leadership across systems',
        )
        self.assertEqual(str(title), 'Staff Software Engineer')
        self.assertTrue(title.is_active)
        self.assertIsNotNone(title.created_at)
        self.assertIsNotNone(title.updated_at)

    def test_job_title_uniqueness(self):
        JobTitle.objects.create(title='DevOps Specialist')
        with self.assertRaises(IntegrityError):
            JobTitle.objects.create(title='DevOps Specialist')

    def test_job_title_ordering(self):
        JobTitle.objects.create(title='QA Analyst')
        JobTitle.objects.create(title='Backend Developer')
        JobTitle.objects.create(title='Cloud Architect')
        titles = list(JobTitle.objects.values_list('title', flat=True))
        self.assertEqual(titles, ['Backend Developer', 'Cloud Architect', 'QA Analyst'])


class EmployeeModelTests(TestCase):
    """Unit and relationship tests for the Employee model."""

    def setUp(self):
        self.dept = Department.objects.create(name='Engineering', description='Core Tech')
        self.job_title = JobTitle.objects.create(title='Software Engineer')
        self.user = User.objects.create_user(
            email='alice@example.com',
            password='StrongPass123!',
            role=User.Role.EMPLOYEE,
        )

    def test_employee_creation_and_str(self):
        emp = Employee.objects.create(
            user=self.user,
            employee_id='EMP001',
            full_name='Alice Smith',
            email='alice@example.com',
            phone='+1-555-0199',
            department=self.dept,
            job_title=self.job_title,
            joining_date=date(2024, 3, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
            base_salary=Decimal('8500.00'),
            address='123 Silicon Blvd, Tech City',
            emergency_contact='Bob Smith (+1-555-0100)',
        )
        self.assertEqual(str(emp), 'Alice Smith (EMP001)')
        self.assertTrue(emp.is_active_employee)
        self.assertEqual(self.user.employee_profile, emp)
        self.assertIn(emp, self.dept.employees.all())
        self.assertIn(emp, self.job_title.employees.all())

    def test_employee_id_uniqueness(self):
        Employee.objects.create(
            employee_id='EMP-DUP',
            full_name='First Employee',
            email='first@example.com',
            joining_date=date(2024, 1, 1),
        )
        with self.assertRaises(IntegrityError):
            Employee.objects.create(
                employee_id='EMP-DUP',
                full_name='Second Employee',
                email='second@example.com',
                joining_date=date(2024, 1, 1),
            )

    def test_employee_email_uniqueness(self):
        Employee.objects.create(
            employee_id='EMP-001',
            full_name='First Employee',
            email='unique@example.com',
            joining_date=date(2024, 1, 1),
        )
        with self.assertRaises(IntegrityError):
            Employee.objects.create(
                employee_id='EMP-002',
                full_name='Second Employee',
                email='unique@example.com',
                joining_date=date(2024, 1, 1),
            )

    def test_employment_status_properties(self):
        emp_active = Employee.objects.create(
            employee_id='EMP-ACT',
            full_name='Active Person',
            email='active@example.com',
            joining_date=date(2024, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
        )
        emp_leave = Employee.objects.create(
            employee_id='EMP-LV',
            full_name='On Leave Person',
            email='leave@example.com',
            joining_date=date(2024, 1, 1),
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
        )
        emp_term = Employee.objects.create(
            employee_id='EMP-TRM',
            full_name='Terminated Person',
            email='term@example.com',
            joining_date=date(2024, 1, 1),
            employment_status=Employee.EmploymentStatus.TERMINATED,
        )
        self.assertTrue(emp_active.is_active_employee)
        self.assertFalse(emp_leave.is_active_employee)
        self.assertFalse(emp_term.is_active_employee)

    def test_department_protect_on_delete(self):
        """Deleting a department with assigned employees should raise ProtectedError."""
        Employee.objects.create(
            employee_id='EMP-DEP',
            full_name='Dept Member',
            email='dept.member@example.com',
            joining_date=date(2024, 1, 1),
            department=self.dept,
        )
        with self.assertRaises(ProtectedError):
            self.dept.delete()

    def test_job_title_protect_on_delete(self):
        """Deleting a job title with assigned employees should raise ProtectedError."""
        Employee.objects.create(
            employee_id='EMP-TITLE',
            full_name='Title Member',
            email='title.member@example.com',
            joining_date=date(2024, 1, 1),
            job_title=self.job_title,
        )
        with self.assertRaises(ProtectedError):
            self.job_title.delete()

    def test_profile_completeness_100_percent(self):
        """When all 10 metric fields are populated, completeness is 100%."""
        emp = Employee.objects.create(
            user=self.user,
            employee_id='EMP-FULL',
            full_name='Full Profile Employee',
            email='full@example.com',
            phone='+1-555-9999',
            department=self.dept,
            job_title=self.job_title,
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('6000.00'),
            address='100 Main Street',
            emergency_contact='Jane Doe 555-1234',
        )
        self.assertEqual(emp.calculate_profile_completeness(), 100)

    def test_profile_completeness_partial(self):
        """Partial profile returns proportionate completeness."""
        # 3 metrics: full_name, email, joining_date => 30%
        emp = Employee.objects.create(
            employee_id='EMP-PARTIAL',
            full_name='Partial Employee',
            email='partial@example.com',
            joining_date=date(2024, 1, 1),
            base_salary=Decimal('0.00'),
        )
        self.assertEqual(emp.calculate_profile_completeness(), 30)

        # Add phone and department => 5 metrics => 50%
        emp.phone = '+1-555-1111'
        emp.department = self.dept
        emp.save()
        self.assertEqual(emp.calculate_profile_completeness(), 50)

    def test_audited_model_mixin_compatibility(self):
        """Verify save() and delete() handle audit kwargs cleanly."""
        emp = Employee(
            employee_id='EMP-AUDIT',
            full_name='Audited Employee',
            email='audit@example.com',
            joining_date=date(2024, 1, 1),
        )
        emp.save(audit_actor=self.user)
        self.assertEqual(emp._audit_actor, self.user)

        emp.delete(audit_actor=self.user)
        self.assertFalse(Employee.objects.filter(employee_id='EMP-AUDIT').exists())
