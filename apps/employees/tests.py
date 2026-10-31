from datetime import date
from decimal import Decimal

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import ProtectedError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from django.urls import reverse

from apps.accounts.models import AuditEvent
from apps.employees.forms import DepartmentForm, EmployeeForm
from apps.employees.models import Department, JobTitle, Employee
from apps.payroll.models import PayrollPeriod, PayrollRecord
from apps.employees.views import (
    department_create,
    department_delete,
    department_edit,
    department_list,
    employee_create,
    employee_detail,
    employee_edit,
    employee_list,
)

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

    def test_department_clean_accepts_active_head(self):
        dept = Department(name='Finance Model')
        emp = Employee.objects.create(
            employee_id='EMP-ACT-HEAD',
            full_name='Active Manager',
            email='active.head@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
        )
        dept.department_head = emp
        dept.full_clean()

    def test_department_clean_rejects_on_leave_head(self):
        dept = Department(name='Finance Model Leave')
        emp = Employee.objects.create(
            employee_id='EMP-LV-HEAD',
            full_name='On Leave Manager',
            email='leave.head@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
        )
        dept.department_head = emp
        with self.assertRaises(ValidationError) as ctx:
            dept.full_clean()
        self.assertIn('department_head', ctx.exception.message_dict)

    def test_department_clean_rejects_terminated_head(self):
        dept = Department(name='Finance Model Term')
        emp = Employee.objects.create(
            employee_id='EMP-TRM-HEAD',
            full_name='Terminated Manager',
            email='term.head@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.TERMINATED,
        )
        dept.department_head = emp
        with self.assertRaises(ValidationError) as ctx:
            dept.full_clean()
        self.assertIn('department_head', ctx.exception.message_dict)

    def test_department_clean_allows_null_head(self):
        dept = Department(name='Finance Model Null', department_head=None)
        dept.full_clean()


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


class EmployeeFormTests(TestCase):
    """Unit tests for EmployeeForm validation and user linking rules."""

    def setUp(self):
        self.dept = Department.objects.create(name='Technology')
        self.job_title = JobTitle.objects.create(title='Software Engineer')
        self.user1 = User.objects.create_user(
            email='user1@example.com',
            password='TestPassword123!',
        )
        self.user2 = User.objects.create_user(
            email='user2@example.com',
            password='TestPassword123!',
        )
        self.existing_emp = Employee.objects.create(
            user=self.user1,
            employee_id='EMP-100',
            full_name='First Employee',
            email='emp1@example.com',
            phone='+1-555-0101',
            department=self.dept,
            job_title=self.job_title,
            joining_date=date(2024, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
            base_salary=Decimal('5000.00'),
        )

    def test_valid_employee_form_without_user(self):
        data = {
            'employee_id': 'EMP-200',
            'full_name': 'Second Employee',
            'email': 'emp2@example.com',
            'phone': '+1-555-0102',
            'department': self.dept.pk,
            'job_title': self.job_title.pk,
            'joining_date': '2024-02-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
            'base_salary': '6000.00',
            'address': '200 Tech Park',
            'emergency_contact': 'Contact Person (+1-555-0199)',
            'user': '',
        }
        form = EmployeeForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        emp = form.save()
        self.assertEqual(emp.employee_id, 'EMP-200')
        self.assertIsNone(emp.user)

    def test_valid_employee_form_with_unlinked_user(self):
        data = {
            'employee_id': 'EMP-201',
            'full_name': 'Third Employee',
            'email': 'emp3@example.com',
            'joining_date': '2024-02-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
            'base_salary': '7000.00',
            'user': self.user2.pk,
        }
        form = EmployeeForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        emp = form.save()
        self.assertEqual(emp.user, self.user2)

    def test_duplicate_employee_id_rejected_case_insensitive(self):
        data = {
            'employee_id': 'emp-100',  # lowercase duplicate
            'full_name': 'Duplicate ID Employee',
            'email': 'unique_email@example.com',
            'joining_date': '2024-03-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
        }
        form = EmployeeForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('employee_id', form.errors)
        self.assertIn('already exists', form.errors['employee_id'][0])

    def test_duplicate_email_rejected_case_insensitive(self):
        data = {
            'employee_id': 'EMP-NEW',
            'full_name': 'Duplicate Email Employee',
            'email': 'EMP1@EXAMPLE.COM',  # uppercase duplicate
            'joining_date': '2024-03-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
        }
        form = EmployeeForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)
        self.assertIn('already exists', form.errors['email'][0])

    def test_edit_same_record_allows_same_id_and_email(self):
        data = {
            'employee_id': 'EMP-100',
            'full_name': 'First Employee Renamed',
            'email': 'emp1@example.com',
            'phone': '+1-555-0999',
            'department': self.dept.pk,
            'job_title': self.job_title.pk,
            'joining_date': '2024-01-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
            'base_salary': '5500.00',
            'user': self.user1.pk,
        }
        form = EmployeeForm(data=data, instance=self.existing_emp)
        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()
        self.assertEqual(updated.full_name, 'First Employee Renamed')

    def test_edit_change_to_existing_duplicate_id_rejected(self):
        other_emp = Employee.objects.create(
            employee_id='EMP-999',
            full_name='Other Person',
            email='other@example.com',
            joining_date=date(2024, 1, 1),
        )
        data = {
            'employee_id': 'EMP-100',  # conflicts with existing_emp
            'full_name': 'Other Person Renamed',
            'email': 'other@example.com',
            'joining_date': '2024-01-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
        }
        form = EmployeeForm(data=data, instance=other_emp)
        self.assertFalse(form.is_valid())
        self.assertIn('employee_id', form.errors)

    def test_edit_change_to_existing_duplicate_email_rejected(self):
        other_emp = Employee.objects.create(
            employee_id='EMP-999',
            full_name='Other Person',
            email='other@example.com',
            joining_date=date(2024, 1, 1),
        )
        data = {
            'employee_id': 'EMP-999',
            'full_name': 'Other Person Renamed',
            'email': 'EMP1@EXAMPLE.COM',  # conflicts with existing_emp
            'joining_date': '2024-01-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
        }
        form = EmployeeForm(data=data, instance=other_emp)
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_user_queryset_contains_only_unlinked_users_on_create(self):
        form = EmployeeForm()
        user_queryset = form.fields['user'].queryset
        self.assertIn(self.user2, user_queryset)
        self.assertNotIn(self.user1, user_queryset)

    def test_user_queryset_includes_currently_linked_user_on_edit(self):
        form = EmployeeForm(instance=self.existing_emp)
        user_queryset = form.fields['user'].queryset
        self.assertIn(self.user1, user_queryset)
        self.assertIn(self.user2, user_queryset)

    def test_cannot_link_user_already_linked_to_another_employee(self):
        data = {
            'employee_id': 'EMP-777',
            'full_name': 'Unauthorized User Link',
            'email': 'emp777@example.com',
            'joining_date': '2024-05-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
            'user': self.user1.pk,  # user1 is already linked to existing_emp
        }
        form = EmployeeForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('user', form.errors)

    def test_negative_salary_rejected(self):
        data = {
            'employee_id': 'EMP-NEG',
            'full_name': 'Negative Salary Person',
            'email': 'neg@example.com',
            'joining_date': '2024-01-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
            'base_salary': '-500.00',
        }
        form = EmployeeForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('base_salary', form.errors)


class DepartmentFormTests(TestCase):
    """Unit tests for DepartmentForm validation and head assignment."""

    def setUp(self):
        self.dept = Department.objects.create(
            name='Human Resources',
            description='People operations and culture',
        )
        self.emp = Employee.objects.create(
            employee_id='EMP-HR-01',
            full_name='HR Manager',
            email='hr.manager@example.com',
            joining_date=date(2024, 1, 1),
        )

    def test_valid_department_form(self):
        data = {
            'name': 'Finance',
            'description': 'Financial planning and accounting',
            'department_head': self.emp.pk,
            'is_active': True,
        }
        form = DepartmentForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        dept = form.save()
        self.assertEqual(dept.name, 'Finance')
        self.assertEqual(dept.department_head, self.emp)
        self.assertTrue(dept.is_active)

    def test_duplicate_department_name_rejected_case_insensitive(self):
        data = {
            'name': 'human resources',  # lowercase duplicate
            'description': 'Duplicate HR department',
            'is_active': True,
        }
        form = DepartmentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)
        self.assertIn('already exists', form.errors['name'][0])

    def test_edit_same_department_allows_same_name(self):
        data = {
            'name': 'Human Resources',
            'description': 'Updated description',
            'is_active': True,
        }
        form = DepartmentForm(data=data, instance=self.dept)
        self.assertTrue(form.is_valid(), form.errors)
        updated = form.save()
        self.assertEqual(updated.description, 'Updated description')

    def test_edit_change_to_existing_department_name_rejected(self):
        other_dept = Department.objects.create(name='Marketing')
        data = {
            'name': 'Human Resources',  # conflicts with self.dept
            'description': 'Attempting duplicate name rename',
            'is_active': True,
        }
        form = DepartmentForm(data=data, instance=other_dept)
        self.assertFalse(form.is_valid())
        self.assertIn('name', form.errors)

    def test_department_head_optional(self):
        data = {
            'name': 'Legal',
            'description': 'Legal compliance',
            'department_head': '',
            'is_active': True,
        }
        form = DepartmentForm(data=data)
        self.assertTrue(form.is_valid(), form.errors)
        dept = form.save()
        self.assertIsNone(dept.department_head)

    def test_department_form_queryset_only_contains_active_employees(self):
        emp_active = Employee.objects.create(
            employee_id='EMP-ACTIVE-Q',
            full_name='Active Candidate',
            email='active.cand@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
        )
        emp_leave = Employee.objects.create(
            employee_id='EMP-LEAVE-Q',
            full_name='On Leave Candidate',
            email='leave.cand@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
        )
        emp_term = Employee.objects.create(
            employee_id='EMP-TERM-Q',
            full_name='Terminated Candidate',
            email='term.cand@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.TERMINATED,
        )
        form = DepartmentForm()
        qs = form.fields['department_head'].queryset
        self.assertIn(emp_active, qs)
        self.assertNotIn(emp_leave, qs)
        self.assertNotIn(emp_term, qs)

    def test_department_form_rejects_on_leave_head_submission(self):
        emp_leave = Employee.objects.create(
            employee_id='EMP-LV-SUB',
            full_name='Leave Person',
            email='leave.sub@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
        )
        data = {
            'name': 'Operations',
            'department_head': emp_leave.pk,
            'is_active': True,
        }
        form = DepartmentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('department_head', form.errors)

    def test_department_form_rejects_terminated_head_submission(self):
        emp_term = Employee.objects.create(
            employee_id='EMP-TRM-SUB',
            full_name='Terminated Person',
            email='term.sub@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.TERMINATED,
        )
        data = {
            'name': 'Operations',
            'department_head': emp_term.pk,
            'is_active': True,
        }
        form = DepartmentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('department_head', form.errors)

    def test_department_form_edit_with_active_head(self):
        active_head = Employee.objects.create(
            employee_id='EMP-ACT-ED',
            full_name='Active Head',
            email='act.head@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
        )
        dept = Department.objects.create(name='Research', department_head=active_head)
        form = DepartmentForm(instance=dept)
        self.assertIn(active_head, form.fields['department_head'].queryset)
        data = {
            'name': 'Research & Innovation',
            'department_head': active_head.pk,
            'is_active': True,
        }
        form_post = DepartmentForm(data=data, instance=dept)
        self.assertTrue(form_post.is_valid(), form_post.errors)
        saved = form_post.save()
        self.assertEqual(saved.department_head, active_head)

    def test_department_form_edit_with_existing_inactive_head(self):
        inactive_head = Employee.objects.create(
            employee_id='EMP-INACT-HEAD',
            full_name='Formerly Active Head',
            email='formerly.active@example.com',
            joining_date=date(2024, 1, 1),
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
        )
        dept = Department.objects.create(name='Legacy Dept', department_head=inactive_head)

        form = DepartmentForm(instance=dept)
        self.assertIn(inactive_head, form.fields['department_head'].queryset)

        data = {
            'name': 'Legacy Dept',
            'department_head': inactive_head.pk,
            'is_active': True,
        }
        form_post = DepartmentForm(data=data, instance=dept)
        self.assertFalse(form_post.is_valid())
        self.assertIn('department_head', form_post.errors)
        self.assertIn('Only active employees may be selected', form_post.errors['department_head'][0])

        data_clear = {
            'name': 'Legacy Dept',
            'department_head': '',
            'is_active': True,
        }
        form_clear = DepartmentForm(data=data_clear, instance=dept)
        self.assertTrue(form_clear.is_valid(), form_clear.errors)
        updated = form_clear.save()
        self.assertIsNone(updated.department_head)


class EmployeeViewTests(TestCase):
    """Unit tests for employee views: RBAC, detail, create, edit, search, filters, pagination."""

    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            email='admin@test.com',
            password='TestPassword123!',
        )
        self.hr_user = User.objects.create_user(
            email='hr@test.com',
            password='TestPassword123!',
            role=User.Role.HR,
        )
        self.employee_user1 = User.objects.create_user(
            email='emp1_user@test.com',
            password='TestPassword123!',
            role=User.Role.EMPLOYEE,
        )
        self.employee_user2 = User.objects.create_user(
            email='emp2_user@test.com',
            password='TestPassword123!',
            role=User.Role.EMPLOYEE,
        )

        self.dept_eng = Department.objects.create(name='Engineering')
        self.dept_sales = Department.objects.create(name='Sales')
        self.job_title = JobTitle.objects.create(title='Engineer')

        self.emp1 = Employee.objects.create(
            user=self.employee_user1,
            employee_id='EMP-001',
            full_name='Alice Smith',
            email='alice@example.com',
            phone='+1-555-0101',
            department=self.dept_eng,
            job_title=self.job_title,
            joining_date=date(2024, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
            base_salary=Decimal('7000.00'),
            address='123 Main St',
            emergency_contact='Bob Smith (+1-555-0100)',
        )
        self.emp2 = Employee.objects.create(
            user=self.employee_user2,
            employee_id='EMP-002',
            full_name='Bob Jones',
            email='bob@example.com',
            phone='+1-555-0102',
            department=self.dept_sales,
            job_title=self.job_title,
            joining_date=date(2024, 2, 1),
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
            base_salary=Decimal('6000.00'),
        )

    def _prepare_request(self, request, user=None):
        request.user = user if user else AnonymousUser()
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        return request

    def _fake_render(self, request, template_name, context=None, status=200):
        resp = HttpResponse(f'rendered {template_name}', status=status)
        resp.template_name = template_name
        resp.context = context or {}
        return resp

    @patch('apps.employees.views.render')
    def test_employee_list_access_admin_and_hr(self, mock_render):
        mock_render.side_effect = self._fake_render

        for role_user in (self.admin_user, self.hr_user):
            with self.subTest(role=role_user.role):
                request = self.factory.get('/employees/')
                self._prepare_request(request, role_user)
                response = employee_list(request)
                self.assertEqual(response.status_code, 200)

    def test_employee_list_access_employee_forbidden(self):
        request = self.factory.get('/employees/')
        self._prepare_request(request, self.employee_user1)
        response = employee_list(request)
        self.assertEqual(response.status_code, 403)

    def test_employee_list_unauthenticated_redirects(self):
        request = self.factory.get('/employees/')
        self._prepare_request(request)
        response = employee_list(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    @patch('apps.employees.views.render')
    def test_employee_list_search_by_name(self, mock_render):
        mock_render.side_effect = self._fake_render
        request = self.factory.get('/employees/?q=Alice')
        self._prepare_request(request, self.hr_user)
        response = employee_list(request)
        self.assertEqual(response.status_code, 200)

        results = list(response.context['page_obj'].object_list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].full_name, 'Alice Smith')

    @patch('apps.employees.views.render')
    def test_employee_list_search_by_email(self, mock_render):
        mock_render.side_effect = self._fake_render
        request = self.factory.get('/employees/?q=bob@example.com')
        self._prepare_request(request, self.hr_user)
        response = employee_list(request)
        self.assertEqual(response.status_code, 200)

        results = list(response.context['page_obj'].object_list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].email, 'bob@example.com')

    @patch('apps.employees.views.render')
    def test_employee_list_search_by_employee_id_case_insensitive(self, mock_render):
        mock_render.side_effect = self._fake_render
        request = self.factory.get('/employees/?q=emp-001')
        self._prepare_request(request, self.hr_user)
        response = employee_list(request)
        self.assertEqual(response.status_code, 200)

        results = list(response.context['page_obj'].object_list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].employee_id, 'EMP-001')

    @patch('apps.employees.views.render')
    def test_employee_list_filter_by_department_id_and_name(self, mock_render):
        mock_render.side_effect = self._fake_render

        # Filter by department ID
        req_id = self.factory.get(f'/employees/?department={self.dept_eng.pk}')
        self._prepare_request(req_id, self.hr_user)
        resp_id = employee_list(req_id)
        results_id = list(resp_id.context['page_obj'].object_list)
        self.assertEqual(len(results_id), 1)
        self.assertEqual(results_id[0], self.emp1)

        # Filter by department name (case-insensitive)
        req_name = self.factory.get('/employees/?department=sales')
        self._prepare_request(req_name, self.hr_user)
        resp_name = employee_list(req_name)
        results_name = list(resp_name.context['page_obj'].object_list)
        self.assertEqual(len(results_name), 1)
        self.assertEqual(results_name[0], self.emp2)

    @patch('apps.employees.views.render')
    def test_employee_list_filter_by_employment_status(self, mock_render):
        mock_render.side_effect = self._fake_render
        request = self.factory.get('/employees/?employment_status=ON_LEAVE')
        self._prepare_request(request, self.hr_user)
        response = employee_list(request)
        self.assertEqual(response.status_code, 200)

        results = list(response.context['page_obj'].object_list)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.emp2)

    @patch('apps.employees.views.render')
    def test_employee_list_pagination_10_per_page(self, mock_render):
        mock_render.side_effect = self._fake_render

        # Create 12 more employees in Engineering (13 in Engineering total)
        for i in range(12):
            Employee.objects.create(
                employee_id=f'EMP-PAG-{i:02d}',
                full_name=f'Paging Employee {i:02d}',
                email=f'paging{i}@example.com',
                department=self.dept_eng,
                joining_date=date(2024, 1, 1),
            )

        # Page 1
        req_p1 = self.factory.get('/employees/?page=1&department=Engineering')
        self._prepare_request(req_p1, self.hr_user)
        resp_p1 = employee_list(req_p1)
        self.assertEqual(len(resp_p1.context['employees']), 10)
        self.assertTrue(resp_p1.context['is_paginated'])
        self.assertEqual(resp_p1.context['pagination_query_string'], 'department=Engineering')

        # Page 2
        req_p2 = self.factory.get('/employees/?page=2&department=Engineering')
        self._prepare_request(req_p2, self.hr_user)
        resp_p2 = employee_list(req_p2)
        self.assertEqual(len(resp_p2.context['employees']), 3)

    @patch('apps.employees.views.render')
    def test_employee_detail_admin_and_hr_can_view_any(self, mock_render):
        mock_render.side_effect = self._fake_render

        for role_user in (self.admin_user, self.hr_user):
            with self.subTest(role=role_user.role):
                request = self.factory.get(f'/employees/{self.emp1.pk}/')
                self._prepare_request(request, role_user)
                response = employee_detail(request, pk=self.emp1.pk)
                self.assertEqual(response.status_code, 200)
                self.assertIn('profile_completeness', response.context)
                self.assertEqual(response.context['profile_completeness'], 100)

    @patch('apps.employees.views.render')
    def test_employee_detail_employee_can_view_own_profile(self, mock_render):
        mock_render.side_effect = self._fake_render
        request = self.factory.get(f'/employees/{self.emp1.pk}/')
        self._prepare_request(request, self.employee_user1)
        response = employee_detail(request, pk=self.emp1.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['is_self'])
        self.assertEqual(response.context['employee'], self.emp1)

    def test_employee_detail_employee_cannot_view_other_profile(self):
        # employee_user1 attempts to view emp2 (owned by employee_user2)
        request = self.factory.get(f'/employees/{self.emp2.pk}/')
        self._prepare_request(request, self.employee_user1)
        response = employee_detail(request, pk=self.emp2.pk)
        self.assertEqual(response.status_code, 403)

    def test_employee_detail_unauthenticated_redirects(self):
        request = self.factory.get(f'/employees/{self.emp1.pk}/')
        self._prepare_request(request)
        response = employee_detail(request, pk=self.emp1.pk)
        self.assertEqual(response.status_code, 302)

    def test_employee_create_hr_success_and_audit_actor(self):
        data = {
            'employee_id': 'EMP-NEW-CREATE',
            'full_name': 'New Created Employee',
            'email': 'newcreated@example.com',
            'phone': '+1-555-9000',
            'department': self.dept_eng.pk,
            'job_title': self.job_title.pk,
            'joining_date': '2024-04-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
            'base_salary': '8500.00',
            'address': '456 Innovation Way',
            'emergency_contact': 'Emergency Contact',
            'user': '',
        }
        request = self.factory.post('/employees/create/', data=data)
        self._prepare_request(request, self.hr_user)
        response = employee_create(request)
        self.assertEqual(response.status_code, 302)

        created_emp = Employee.objects.get(employee_id='EMP-NEW-CREATE')
        self.assertEqual(created_emp.full_name, 'New Created Employee')
        ct = ContentType.objects.get_for_model(Employee)
        audit_event = AuditEvent.objects.filter(
            content_type=ct,
            object_id=created_emp.pk,
            action=AuditEvent.Action.CREATE,
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor, self.hr_user)

    @patch('apps.employees.views.render')
    def test_employee_create_invalid_form_rerenders(self, mock_render):
        mock_render.side_effect = self._fake_render
        data = {
            'employee_id': 'EMP-INVALID',
            # missing full_name, email, joining_date
        }
        request = self.factory.post('/employees/create/', data=data)
        self._prepare_request(request, self.hr_user)
        response = employee_create(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, 'employees/employee_form.html')
        self.assertFalse(response.context['form'].is_valid())

    def test_employee_create_employee_role_forbidden(self):
        data = {
            'employee_id': 'EMP-FORBIDDEN',
            'full_name': 'Forbidden Employee',
            'email': 'forbidden@example.com',
            'joining_date': '2024-01-01',
        }
        request = self.factory.post('/employees/create/', data=data)
        self._prepare_request(request, self.employee_user1)
        response = employee_create(request)
        self.assertEqual(response.status_code, 403)

    def test_employee_edit_hr_success_and_audit_actor(self):
        data = {
            'employee_id': 'EMP-001',
            'full_name': 'Alice Smith Edited',
            'email': 'alice@example.com',
            'phone': '+1-555-0999',
            'department': self.dept_eng.pk,
            'job_title': self.job_title.pk,
            'joining_date': '2024-01-01',
            'employment_status': Employee.EmploymentStatus.ACTIVE,
            'base_salary': '7500.00',
            'address': '123 Main St Edited',
            'emergency_contact': 'Bob Smith (+1-555-0100)',
            'user': self.employee_user1.pk,
        }
        request = self.factory.post(f'/employees/{self.emp1.pk}/edit/', data=data)
        self._prepare_request(request, self.hr_user)
        response = employee_edit(request, pk=self.emp1.pk)
        self.assertEqual(response.status_code, 302)

        self.emp1.refresh_from_db()
        self.assertEqual(self.emp1.full_name, 'Alice Smith Edited')
        self.assertEqual(self.emp1.base_salary, Decimal('7500.00'))
        ct = ContentType.objects.get_for_model(Employee)
        audit_event = AuditEvent.objects.filter(
            content_type=ct,
            object_id=self.emp1.pk,
            action=AuditEvent.Action.UPDATE,
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor, self.hr_user)

    def test_employee_edit_employee_role_forbidden(self):
        data = {
            'employee_id': 'EMP-001',
            'full_name': 'Hacker Edit',
            'email': 'alice@example.com',
            'joining_date': '2024-01-01',
        }
        request = self.factory.post(f'/employees/{self.emp1.pk}/edit/', data=data)
        self._prepare_request(request, self.employee_user1)
        response = employee_edit(request, pk=self.emp1.pk)
        self.assertEqual(response.status_code, 403)


class DepartmentViewTests(TestCase):
    """Unit tests for Department CRUD views: permissions, creation, update, and protected deletion."""

    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            email='dept_admin@test.com',
            password='TestPassword123!',
        )
        self.hr_user = User.objects.create_user(
            email='dept_hr@test.com',
            password='TestPassword123!',
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            email='dept_emp@test.com',
            password='TestPassword123!',
            role=User.Role.EMPLOYEE,
        )

        self.dept = Department.objects.create(
            name='Engineering',
            description='Core Tech',
        )
        self.emp = Employee.objects.create(
            employee_id='EMP-D01',
            full_name='Staff Member',
            email='staff@example.com',
            department=self.dept,
            joining_date=date(2024, 1, 1),
        )

    def _prepare_request(self, request, user=None):
        request.user = user if user else AnonymousUser()
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        return request

    def _fake_render(self, request, template_name, context=None, status=200):
        resp = HttpResponse(f'rendered {template_name}', status=status)
        resp.template_name = template_name
        resp.context = context or {}
        return resp

    @patch('apps.employees.views.render')
    def test_department_list_access_admin_and_hr(self, mock_render):
        mock_render.side_effect = self._fake_render

        for role_user in (self.admin_user, self.hr_user):
            with self.subTest(role=role_user.role):
                request = self.factory.get('/employees/departments/')
                self._prepare_request(request, role_user)
                response = department_list(request)
                self.assertEqual(response.status_code, 200)

                departments = list(response.context['departments'])
                self.assertEqual(len(departments), 1)
                self.assertEqual(departments[0].employee_count, 1)

    def test_department_list_employee_forbidden(self):
        request = self.factory.get('/employees/departments/')
        self._prepare_request(request, self.employee_user)
        response = department_list(request)
        self.assertEqual(response.status_code, 403)

    def test_department_list_unauthenticated_redirects(self):
        request = self.factory.get('/employees/departments/')
        self._prepare_request(request)
        response = department_list(request)
        self.assertEqual(response.status_code, 302)

    def test_department_create_hr_success_and_audit(self):
        data = {
            'name': 'Marketing',
            'description': 'Brand and growth',
            'department_head': self.emp.pk,
            'is_active': True,
        }
        request = self.factory.post('/employees/departments/create/', data=data)
        self._prepare_request(request, self.hr_user)
        response = department_create(request)
        self.assertEqual(response.status_code, 302)

        created_dept = Department.objects.get(name='Marketing')
        self.assertEqual(created_dept.department_head, self.emp)

        ct = ContentType.objects.get_for_model(Department)
        audit_event = AuditEvent.objects.filter(
            content_type=ct,
            object_id=created_dept.pk,
            action=AuditEvent.Action.CREATE,
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor, self.hr_user)

    @patch('apps.employees.views.render')
    def test_department_create_invalid_form_rerenders(self, mock_render):
        mock_render.side_effect = self._fake_render
        data = {'name': ''}  # empty required name
        request = self.factory.post('/employees/departments/create/', data=data)
        self._prepare_request(request, self.hr_user)
        response = department_create(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, 'employees/department_form.html')
        self.assertFalse(response.context['form'].is_valid())

    def test_department_create_employee_forbidden(self):
        data = {'name': 'Unauthorized Dept'}
        request = self.factory.post('/employees/departments/create/', data=data)
        self._prepare_request(request, self.employee_user)
        response = department_create(request)
        self.assertEqual(response.status_code, 403)

    def test_department_edit_hr_success_and_audit(self):
        data = {
            'name': 'Engineering & Research',
            'description': 'Advanced Technology',
            'is_active': True,
        }
        request = self.factory.post(f'/employees/departments/{self.dept.pk}/edit/', data=data)
        self._prepare_request(request, self.hr_user)
        response = department_edit(request, pk=self.dept.pk)
        self.assertEqual(response.status_code, 302)

        self.dept.refresh_from_db()
        self.assertEqual(self.dept.name, 'Engineering & Research')
        self.assertEqual(self.dept.description, 'Advanced Technology')

        ct = ContentType.objects.get_for_model(Department)
        audit_event = AuditEvent.objects.filter(
            content_type=ct,
            object_id=self.dept.pk,
            action=AuditEvent.Action.UPDATE,
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor, self.hr_user)

    def test_department_edit_employee_forbidden(self):
        data = {'name': 'Hacker Dept'}
        request = self.factory.post(f'/employees/departments/{self.dept.pk}/edit/', data=data)
        self._prepare_request(request, self.employee_user)
        response = department_edit(request, pk=self.dept.pk)
        self.assertEqual(response.status_code, 403)

    @patch('apps.employees.views.render')
    def test_department_delete_get_renders_confirmation_and_does_not_delete(self, mock_render):
        mock_render.side_effect = self._fake_render
        request = self.factory.get(f'/employees/departments/{self.dept.pk}/delete/')
        self._prepare_request(request, self.hr_user)
        response = department_delete(request, pk=self.dept.pk)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, 'employees/department_confirm_delete.html')
        self.assertTrue(response.context['has_assigned_employees'])
        self.assertTrue(Department.objects.filter(pk=self.dept.pk).exists())

    def test_department_delete_assigned_employees_blocked(self):
        # self.dept has self.emp assigned
        request = self.factory.post(f'/employees/departments/{self.dept.pk}/delete/')
        self._prepare_request(request, self.hr_user)
        response = department_delete(request, pk=self.dept.pk)
        self.assertEqual(response.status_code, 302)

        # Department must still exist
        self.assertTrue(Department.objects.filter(pk=self.dept.pk).exists())

    def test_department_delete_unassigned_success_and_audit(self):
        empty_dept = Department.objects.create(name='Temporary Dept')
        empty_dept_id = empty_dept.pk

        request = self.factory.post(f'/employees/departments/{empty_dept_id}/delete/')
        self._prepare_request(request, self.hr_user)
        response = department_delete(request, pk=empty_dept_id)
        self.assertEqual(response.status_code, 302)

        self.assertFalse(Department.objects.filter(pk=empty_dept_id).exists())

        ct = ContentType.objects.get_for_model(Department)
        audit_event = AuditEvent.objects.filter(
            content_type=ct,
            object_id=empty_dept_id,
            action=AuditEvent.Action.DELETE,
        ).first()
        self.assertIsNotNone(audit_event)
        self.assertEqual(audit_event.actor, self.hr_user)

    def test_department_delete_employee_forbidden(self):
        request = self.factory.post(f'/employees/departments/{self.dept.pk}/delete/')
        self._prepare_request(request, self.employee_user)
        response = department_delete(request, pk=self.dept.pk)
        self.assertEqual(response.status_code, 403)

    def test_department_create_crafted_post_with_ineligible_head_rejected(self):
        emp_leave = Employee.objects.create(
            employee_id='EMP-CRAFT-01',
            full_name='Crafted Leave',
            email='crafted.leave@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
        )
        data = {
            'name': 'Crafted Dept',
            'department_head': emp_leave.pk,
            'is_active': True,
        }
        request = self.factory.post('/employees/departments/create/', data=data)
        self._prepare_request(request, self.hr_user)
        response = department_create(request)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Department.objects.filter(name='Crafted Dept').exists())

    def test_department_edit_crafted_post_with_ineligible_head_rejected(self):
        emp_term = Employee.objects.create(
            employee_id='EMP-CRAFT-02',
            full_name='Crafted Terminated',
            email='crafted.term@example.com',
            joining_date=date(2025, 1, 1),
            employment_status=Employee.EmploymentStatus.TERMINATED,
        )
        data = {
            'name': self.dept.name,
            'department_head': emp_term.pk,
            'is_active': True,
        }
        request = self.factory.post(f'/employees/departments/{self.dept.pk}/edit/', data=data)
        self._prepare_request(request, self.hr_user)
        response = department_edit(request, pk=self.dept.pk)
        self.assertEqual(response.status_code, 200)
        self.dept.refresh_from_db()
        self.assertNotEqual(self.dept.department_head, emp_term)

    def test_department_delete_blocked_when_on_leave_or_terminated_employee_assigned(self):
        leave_dept = Department.objects.create(name='Leave Dept')
        Employee.objects.create(
            employee_id='EMP-DEP-LV',
            full_name='Assigned Leave Employee',
            email='assigned.leave@example.com',
            joining_date=date(2025, 1, 1),
            department=leave_dept,
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
        )
        request = self.factory.post(f'/employees/departments/{leave_dept.pk}/delete/')
        self._prepare_request(request, self.hr_user)
        response = department_delete(request, pk=leave_dept.pk)
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Department.objects.filter(pk=leave_dept.pk).exists())



class EmployeeIntegrationAndTemplateTests(TestCase):
    """End-to-end integration and template rendering tests using Django test client."""

    def setUp(self):
        self.hr = User.objects.create_user(
            email='hr_client@test.com',
            password='TestPassword123!',
            role=User.Role.HR,
        )
        self.employee_user = User.objects.create_user(
            email='emp_client@test.com',
            password='TestPassword123!',
            role=User.Role.EMPLOYEE,
        )
        self.dept = Department.objects.create(
            name='Engineering',
            description='Tech Division',
        )
        self.job = JobTitle.objects.create(title='Lead Architect')
        self.emp = Employee.objects.create(
            user=self.employee_user,
            employee_id='EMP-CLI-01',
            full_name='Clara Barton',
            email='clara@example.com',
            phone='+1-555-4321',
            department=self.dept,
            job_title=self.job,
            joining_date=date(2024, 1, 1),
            employment_status=Employee.EmploymentStatus.ACTIVE,
            base_salary=Decimal('9000.00'),
            address='789 Nurse Way',
            emergency_contact='Emergency Contact',
        )

    def test_employee_list_renders_correct_template_and_badges(self):
        self.client.force_login(self.hr)
        url = reverse('employees:employee_list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'employees/employee_list.html')
        self.assertContains(response, 'Clara Barton')
        self.assertContains(response, 'EMP-CLI-01')
        self.assertContains(response, 'Active')

    def test_employee_detail_renders_progress_bar_and_completeness(self):
        self.client.force_login(self.hr)
        url = reverse('employees:employee_detail', args=[self.emp.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'employees/employee_detail.html')
        self.assertContains(response, 'Profile Completeness')
        self.assertContains(response, '100%')
        self.assertContains(response, 'progress-bar')

    def test_employee_create_and_edit_templates(self):
        self.client.force_login(self.hr)

        # GET create
        create_url = reverse('employees:employee_create')
        res_create = self.client.get(create_url)
        self.assertEqual(res_create.status_code, 200)
        self.assertTemplateUsed(res_create, 'employees/employee_form.html')
        self.assertContains(res_create, 'Create Employee')

        # GET edit
        edit_url = reverse('employees:employee_edit', args=[self.emp.pk])
        res_edit = self.client.get(edit_url)
        self.assertEqual(res_edit.status_code, 200)
        self.assertTemplateUsed(res_edit, 'employees/employee_form.html')
        self.assertContains(res_edit, 'Save Changes')

    def test_department_templates_and_deletion_protection_page(self):
        self.client.force_login(self.hr)

        # Department list
        dept_list_url = reverse('employees:department_list')
        res_list = self.client.get(dept_list_url)
        self.assertEqual(res_list.status_code, 200)
        self.assertTemplateUsed(res_list, 'employees/department_list.html')
        self.assertContains(res_list, 'Engineering')

        # Department create
        dept_create_url = reverse('employees:department_create')
        res_create = self.client.get(dept_create_url)
        self.assertEqual(res_create.status_code, 200)
        self.assertTemplateUsed(res_create, 'employees/department_form.html')

        # Department delete confirmation with assigned employees
        dept_del_url = reverse('employees:department_delete', args=[self.dept.pk])
        res_del = self.client.get(dept_del_url)
        self.assertEqual(res_del.status_code, 200)
        self.assertTemplateUsed(res_del, 'employees/department_confirm_delete.html')
        self.assertContains(res_del, 'Deletion Blocked by Referential Integrity')
        self.assertContains(res_del, 'departments with assigned employees cannot be deleted')
        self.assertNotContains(res_del, 'departments with active employees cannot be deleted')

    def test_job_title_html_is_escaped_against_xss(self):
        xss_job = JobTitle.objects.create(title='<script>alert("xss")</script>')
        Employee.objects.create(
            employee_id='EMP-XSS-01',
            full_name='XSS Target',
            email='xss@example.com',
            joining_date=date(2025, 1, 1),
            job_title=xss_job,
            employment_status=Employee.EmploymentStatus.ACTIVE,
        )
        self.client.force_login(self.hr)
        url = reverse('employees:employee_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        # Verify raw script tag is not rendered
        self.assertNotContains(response, '<script>alert("xss")</script>')
        # Verify escaped text is rendered instead of executable HTML
        self.assertContains(response, '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;')

    def test_employee_list_unassigned_job_title_renders_fallback_html(self):
        Employee.objects.create(
            employee_id='EMP-NOJOB-01',
            full_name='No Job Employee',
            email='nojob@example.com',
            joining_date=date(2025, 1, 1),
            job_title=None,
            employment_status=Employee.EmploymentStatus.ACTIVE,
        )
        self.client.force_login(self.hr)
        url = reverse('employees:employee_list')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<span class="text-muted small">Unassigned</span>')

    def test_department_delete_warning_wording_accurate_for_assigned_employees(self):
        dept_with_inactive = Department.objects.create(name='Inactive Staff Dept')
        Employee.objects.create(
            employee_id='EMP-INACT-DEL',
            full_name='Terminated Assigned',
            email='term.del@example.com',
            joining_date=date(2025, 1, 1),
            department=dept_with_inactive,
            employment_status=Employee.EmploymentStatus.TERMINATED,
        )
        self.client.force_login(self.hr)
        dept_del_url = reverse('employees:department_delete', args=[dept_with_inactive.pk])
        res_del = self.client.get(dept_del_url)
        self.assertEqual(res_del.status_code, 200)
        self.assertTemplateUsed(res_del, 'employees/department_confirm_delete.html')
        self.assertContains(res_del, 'Deletion Blocked by Referential Integrity')
        self.assertContains(res_del, 'departments with assigned employees cannot be deleted')
        self.assertNotContains(res_del, 'departments with active employees cannot be deleted')


class EmployeePayrollIntegrationTests(TestCase):
    """
    Week 3 Integration tests verifying the contract between apps.employees and apps.payroll:
    - ForeignKey and reverse relationships
    - Base salary availability and precision
    - Compatibility aliases (basic_salary)
    - Historical snapshot preservation on employee salary updates
    - Protected deletion for employees with payroll history
    - Department salary rollups and active employee filtering
    """

    def setUp(self):
        self.dept = Department.objects.create(name='Finance & Operations')
        self.job = JobTitle.objects.create(title='Financial Analyst')
        self.employee = Employee.objects.create(
            employee_id='EMP-PAY-01',
            full_name='Jordan Lee',
            email='jordan.lee@example.com',
            joining_date=date(2026, 1, 1),
            department=self.dept,
            job_title=self.job,
            employment_status=Employee.EmploymentStatus.ACTIVE,
            base_salary=Decimal('45000.00'),
        )
        self.period_oct = PayrollPeriod.objects.create(
            name='October 2026',
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 31),
        )
        self.period_nov = PayrollPeriod.objects.create(
            name='November 2026',
            start_date=date(2026, 11, 1),
            end_date=date(2026, 11, 30),
        )

    def test_payroll_record_foreign_key_to_employee_and_base_salary(self):
        """PayrollRecord successfully references Employee and reads employee base_salary."""
        record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period_oct,
            basic_salary=self.employee.base_salary,
            total_allowances=Decimal('3500.00'),
            total_deductions=Decimal('1500.00'),
        )
        self.assertEqual(record.employee, self.employee)
        self.assertEqual(record.basic_salary, Decimal('45000.00'))
        self.assertEqual(record.gross_salary, Decimal('48500.00'))
        self.assertEqual(record.net_salary, Decimal('47000.00'))

    def test_employee_payroll_records_reverse_relationship(self):
        """Employee model accesses its payroll history via the payroll_records related name."""
        record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period_oct,
            basic_salary=self.employee.base_salary,
        )
        self.assertIn(record, self.employee.payroll_records.all())
        self.assertEqual(self.employee.payroll_records.count(), 1)

    def test_employee_basic_salary_property_alias(self):
        """Employee provides basic_salary property getter/setter for compatibility with payroll naming."""
        self.assertEqual(self.employee.basic_salary, Decimal('45000.00'))
        self.assertEqual(self.employee.basic_salary, self.employee.base_salary)

        # Setter updates base_salary
        self.employee.basic_salary = Decimal('52000.00')
        self.assertEqual(self.employee.base_salary, Decimal('52000.00'))

    def test_employee_get_base_salary_method(self):
        """get_base_salary() returns base_salary with proper Decimal type."""
        salary = self.employee.get_base_salary()
        self.assertIsInstance(salary, Decimal)
        self.assertEqual(salary, Decimal('45000.00'))

    def test_salary_decimal_precision_is_preserved(self):
        """Financial precision to two decimal places is strictly maintained without floating point drift."""
        precise_emp = Employee.objects.create(
            employee_id='EMP-PREC',
            full_name='Precision Employee',
            email='precision@example.com',
            joining_date=date(2026, 2, 1),
            base_salary=Decimal('12345.67'),
        )
        record = PayrollRecord.objects.create(
            employee=precise_emp,
            payroll_period=self.period_oct,
            basic_salary=precise_emp.base_salary,
            total_allowances=Decimal('0.33'),
            total_deductions=Decimal('100.00'),
        )
        self.assertEqual(record.basic_salary, Decimal('12345.67'))
        self.assertEqual(record.gross_salary, Decimal('12346.00'))
        self.assertEqual(record.net_salary, Decimal('12246.00'))

    def test_updating_employee_base_salary_preserves_historical_snapshots(self):
        """
        Modifying an employee's base salary updates future payroll records while
        leaving past historical PayrollRecord snapshots completely intact.
        """
        historical_record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period_oct,
            basic_salary=self.employee.base_salary,
        )
        self.assertEqual(historical_record.basic_salary, Decimal('45000.00'))

        self.employee.base_salary = Decimal('55000.00')
        self.employee.save()
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.base_salary, Decimal('55000.00'))

        future_record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period_nov,
            basic_salary=self.employee.base_salary,
        )

        historical_record.refresh_from_db()
        self.assertEqual(historical_record.basic_salary, Decimal('45000.00'))
        self.assertEqual(future_record.basic_salary, Decimal('55000.00'))

    def test_employee_with_payroll_records_cannot_be_deleted(self):
        """ProtectedError is raised when attempting to delete an employee with existing payroll records."""
        PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period_oct,
            basic_salary=self.employee.base_salary,
        )
        with self.assertRaises(ProtectedError):
            self.employee.delete()

    def test_zero_salary_employee_payroll_integration(self):
        """A valid zero salary is handled correctly by both employee and payroll models."""
        intern = Employee.objects.create(
            employee_id='EMP-INT-01',
            full_name='Unpaid Intern',
            email='intern@example.com',
            joining_date=date(2026, 6, 1),
            base_salary=Decimal('0.00'),
        )
        record = PayrollRecord.objects.create(
            employee=intern,
            payroll_period=self.period_oct,
            basic_salary=intern.base_salary,
            total_allowances=Decimal('500.00'),
            total_deductions=Decimal('0.00'),
        )
        self.assertEqual(record.basic_salary, Decimal('0.00'))
        self.assertEqual(record.gross_salary, Decimal('500.00'))
        self.assertEqual(record.net_salary, Decimal('500.00'))

    def test_on_leave_and_terminated_employee_payroll_records(self):
        """Employees on leave or terminated maintain their relationship with historical payroll records."""
        record = PayrollRecord.objects.create(
            employee=self.employee,
            payroll_period=self.period_oct,
            basic_salary=self.employee.base_salary,
        )

        self.employee.employment_status = Employee.EmploymentStatus.ON_LEAVE
        self.employee.save()
        self.assertEqual(self.employee.payroll_records.first(), record)

        self.employee.employment_status = Employee.EmploymentStatus.TERMINATED
        self.employee.save()
        self.assertEqual(self.employee.payroll_records.first(), record)

    def test_department_total_base_salary_property(self):
        """Department.total_base_salary correctly aggregates the base salaries of active department members."""
        Employee.objects.create(
            employee_id='EMP-PAY-02',
            full_name='Alex Rivera',
            email='alex.rivera@example.com',
            joining_date=date(2026, 1, 15),
            department=self.dept,
            employment_status=Employee.EmploymentStatus.ACTIVE,
            base_salary=Decimal('35000.00'),
        )
        self.assertEqual(self.dept.total_base_salary, Decimal('80000.00'))

    def test_department_total_base_salary_excludes_terminated_employees(self):
        """Terminated employees are excluded from department total base salary rollup."""
        Employee.objects.create(
            employee_id='EMP-PAY-TERM',
            full_name='Former Employee',
            email='former@example.com',
            joining_date=date(2025, 1, 1),
            department=self.dept,
            employment_status=Employee.EmploymentStatus.TERMINATED,
            base_salary=Decimal('100000.00'),
        )
        self.assertEqual(self.dept.total_base_salary, Decimal('45000.00'))

    def test_department_total_base_salary_empty_department(self):
        """Department with no employees returns Decimal('0.00') without errors."""
        empty_dept = Department.objects.create(name='New Empty Department')
        self.assertEqual(empty_dept.total_base_salary, Decimal('0.00'))


class EmployeeModelCleanAndValidationTests(TestCase):
    """
    Unit tests for model-level clean() validation, save normalization, and profile completeness:
    - Non-negative salary validation
    - Case-insensitive uniqueness for employee ID, email, and department name
    - User account linking validation
    - Department head employment status validation
    - Robust profile completeness calculation ignoring whitespace
    """

    def setUp(self):
        self.dept = Department.objects.create(name='Technology')
        self.job = JobTitle.objects.create(title='DevOps Engineer')
        self.user1 = User.objects.create_user(email='user_val1@example.com', password='TestPassword123!')
        self.user2 = User.objects.create_user(email='user_val2@example.com', password='TestPassword123!')
        self.employee = Employee.objects.create(
            user=self.user1,
            employee_id='EMP-VAL-01',
            full_name='Morgan Stark',
            email='morgan@example.com',
            joining_date=date(2026, 1, 1),
            department=self.dept,
            job_title=self.job,
            base_salary=Decimal('8000.00'),
        )

    def test_employee_clean_rejects_negative_salary(self):
        """Employee.clean() raises ValidationError if base_salary is negative."""
        emp = Employee(
            employee_id='EMP-NEG-01',
            full_name='Negative Salary Test',
            email='negtest@example.com',
            joining_date=date(2026, 1, 1),
            base_salary=Decimal('-100.00'),
        )
        with self.assertRaises(ValidationError) as ctx:
            emp.clean()
        self.assertIn('base_salary', ctx.exception.message_dict)

    def test_employee_clean_rejects_case_insensitive_duplicate_employee_id(self):
        """Employee.clean() rejects duplicate employee IDs regardless of case."""
        dup_emp = Employee(
            employee_id='emp-val-01',
            full_name='Duplicate ID Test',
            email='dup_id@example.com',
            joining_date=date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            dup_emp.clean()
        self.assertIn('employee_id', ctx.exception.message_dict)

    def test_employee_clean_rejects_case_insensitive_duplicate_email(self):
        """Employee.clean() rejects duplicate emails regardless of case."""
        dup_emp = Employee(
            employee_id='EMP-VAL-99',
            full_name='Duplicate Email Test',
            email='MORGAN@EXAMPLE.COM',
            joining_date=date(2026, 1, 1),
        )
        with self.assertRaises(ValidationError) as ctx:
            dup_emp.clean()
        self.assertIn('email', ctx.exception.message_dict)

    def test_employee_clean_allows_own_id_and_email_on_update(self):
        """Calling clean() on an existing record with the same ID and email succeeds."""
        self.employee.full_name = 'Morgan Stark Updated'
        try:
            self.employee.clean()
        except ValidationError:
            self.fail('clean() raised ValidationError unexpectedly on valid update.')

    def test_employee_clean_rejects_linking_already_linked_user(self):
        """Employee.clean() rejects assigning a user account already assigned to another employee."""
        emp2 = Employee(
            employee_id='EMP-VAL-02',
            full_name='Second Person',
            email='second@example.com',
            joining_date=date(2026, 1, 1),
            user=self.user1,
        )
        with self.assertRaises(ValidationError) as ctx:
            emp2.clean()
        self.assertIn('user', ctx.exception.message_dict)

    def test_employee_save_strips_id_and_lowercases_email(self):
        """Employee.save() normalizes whitespace from employee_id and lowercases email."""
        emp = Employee.objects.create(
            employee_id='  EMP-TRIM-01  ',
            full_name='Trim Test',
            email='  Trim.User@Domain.COM  ',
            joining_date=date(2026, 1, 1),
            base_salary=Decimal('5000.00'),
        )
        self.assertEqual(emp.employee_id, 'EMP-TRIM-01')
        self.assertEqual(emp.email, 'trim.user@domain.com')

    def test_department_clean_rejects_duplicate_name_case_insensitive(self):
        """Department.clean() rejects duplicate department names case-insensitively."""
        dup_dept = Department(name='technology')
        with self.assertRaises(ValidationError) as ctx:
            dup_dept.clean()
        self.assertIn('name', ctx.exception.message_dict)

    def test_department_clean_rejects_terminated_department_head(self):
        """Department.clean() rejects assigning a terminated employee as department head."""
        terminated_emp = Employee.objects.create(
            employee_id='EMP-TERM-HEAD',
            full_name='Terminated Head',
            email='termhead@example.com',
            joining_date=date(2026, 1, 1),
            employment_status=Employee.EmploymentStatus.TERMINATED,
        )
        dept = Department(name='Operations', department_head=terminated_emp)
        with self.assertRaises(ValidationError) as ctx:
            dept.clean()
        self.assertIn('department_head', ctx.exception.message_dict)

    def test_department_save_strips_name(self):
        """Department.save() trims extraneous whitespace from department name."""
        dept = Department.objects.create(name='  Legal Affairs  ')
        self.assertEqual(dept.name, 'Legal Affairs')

    def test_job_title_clean_rejects_duplicate_title_case_insensitive(self):
        """JobTitle.clean() rejects duplicate job titles case-insensitively."""
        dup_job = JobTitle(title='devops engineer')
        with self.assertRaises(ValidationError) as ctx:
            dup_job.clean()
        self.assertIn('title', ctx.exception.message_dict)

    def test_job_title_save_strips_title(self):
        """JobTitle.save() trims extraneous whitespace from job title."""
        job = JobTitle.objects.create(title='  Cloud Architect  ')
        self.assertEqual(job.title, 'Cloud Architect')

    def test_profile_completeness_ignores_whitespace_strings(self):
        """Profile completeness treats whitespace-only strings as incomplete."""
        emp = Employee.objects.create(
            employee_id='EMP-SPACE',
            full_name='Space Employee',
            email='space@example.com',
            phone='   ',
            address='   \n  ',
            emergency_contact='   ',
            joining_date=date(2026, 1, 1),
            base_salary=Decimal('0.00'),
        )
        self.assertEqual(emp.calculate_profile_completeness(), 30)


class EmployeeViewAndSecurityExtendedTests(TestCase):
    """
    Extended view and security tests:
    - 404 handling on missing resources
    - URL aliases resolution
    - Department head termination validation in DepartmentForm
    - Employee status filtering case-insensitivity
    - Own-profile salary visibility
    """

    def setUp(self):
        self.factory = RequestFactory()
        self.hr_user = User.objects.create_user(
            email='ext_hr@example.com',
            password='TestPassword123!',
            role=User.Role.HR,
        )
        self.emp_user = User.objects.create_user(
            email='ext_emp@example.com',
            password='TestPassword123!',
            role=User.Role.EMPLOYEE,
        )
        self.dept = Department.objects.create(name='Customer Success')
        self.employee = Employee.objects.create(
            user=self.emp_user,
            employee_id='EMP-EXT-01',
            full_name='Taylor Swift',
            email='taylor@example.com',
            joining_date=date(2026, 1, 1),
            department=self.dept,
            base_salary=Decimal('95000.00'),
            employment_status=Employee.EmploymentStatus.ON_LEAVE,
        )

    def _prepare_request(self, request, user=None):
        request.user = user if user else AnonymousUser()
        SessionMiddleware(lambda r: None).process_request(request)
        MessageMiddleware(lambda r: None).process_request(request)
        return request

    def _fake_render(self, request, template_name, context=None, status=200):
        resp = HttpResponse(f'rendered {template_name}', status=status)
        resp.template_name = template_name
        resp.context = context or {}
        return resp

    def test_employee_detail_404_for_nonexistent_employee(self):
        """Accessing a nonexistent employee ID raises Http404."""
        request = self.factory.get('/employees/99999/')
        self._prepare_request(request, self.hr_user)
        from django.http import Http404
        with self.assertRaises(Http404):
            employee_detail(request, pk=99999)

    def test_employee_edit_404_for_nonexistent_employee(self):
        """Editing a nonexistent employee ID raises Http404."""
        request = self.factory.get('/employees/99999/edit/')
        self._prepare_request(request, self.hr_user)
        from django.http import Http404
        with self.assertRaises(Http404):
            employee_edit(request, pk=99999)

    def test_department_edit_404_for_nonexistent_department(self):
        """Editing a nonexistent department ID raises Http404."""
        request = self.factory.get('/employees/departments/99999/edit/')
        self._prepare_request(request, self.hr_user)
        from django.http import Http404
        with self.assertRaises(Http404):
            department_edit(request, pk=99999)

    def test_department_delete_404_for_nonexistent_department(self):
        """Deleting a nonexistent department ID raises Http404."""
        request = self.factory.get('/employees/departments/99999/delete/')
        self._prepare_request(request, self.hr_user)
        from django.http import Http404
        with self.assertRaises(Http404):
            department_delete(request, pk=99999)

    def test_url_aliases_reverse_resolution(self):
        """Both canonical and alias URL route names resolve without NoReverseMatch."""
        self.assertEqual(reverse('employees:employee_detail', args=[self.employee.pk]), f'/employees/{self.employee.pk}/')
        self.assertEqual(reverse('employees:detail', args=[self.employee.pk]), f'/employees/{self.employee.pk}/')
        self.assertEqual(reverse('employees:employee_create'), '/employees/create/')
        self.assertEqual(reverse('employees:create'), '/employees/create/')
        self.assertEqual(reverse('employees:employee_edit', args=[self.employee.pk]), f'/employees/{self.employee.pk}/edit/')
        self.assertEqual(reverse('employees:edit', args=[self.employee.pk]), f'/employees/{self.employee.pk}/edit/')
        self.assertEqual(reverse('employees:department_list'), '/employees/departments/')
        self.assertEqual(reverse('employees:departments'), '/employees/departments/list/')

    def test_department_form_rejects_terminated_department_head(self):
        """DepartmentForm rejects assigning a terminated employee as department head."""
        term_emp = Employee.objects.create(
            employee_id='EMP-FORM-TERM',
            full_name='Terminated Candidate',
            email='termcand@example.com',
            joining_date=date(2026, 1, 1),
            employment_status=Employee.EmploymentStatus.TERMINATED,
        )
        data = {
            'name': 'Infrastructure Team',
            'department_head': term_emp.pk,
            'is_active': True,
        }
        form = DepartmentForm(data=data)
        self.assertFalse(form.is_valid())
        self.assertIn('department_head', form.errors)

    @patch('apps.employees.views.render')
    def test_employee_list_filter_status_case_insensitive_and_normalized(self, mock_render):
        """Lowercase status query parameter ?employment_status=on_leave filters and normalizes selected_status."""
        mock_render.side_effect = self._fake_render
        request = self.factory.get('/employees/?employment_status=on_leave')
        self._prepare_request(request, self.hr_user)
        response = employee_list(request)
        self.assertEqual(response.status_code, 200)

        self.assertEqual(response.context['selected_status'], 'ON_LEAVE')
        results = list(response.context['page_obj'].object_list)
        self.assertIn(self.employee, results)

    def test_employee_detail_own_profile_shows_salary_to_employee(self):
        """Employee viewing their own profile using test client receives template with base salary visible."""
        self.client.force_login(self.emp_user)
        url = reverse('employees:employee_detail', args=[self.employee.pk])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Base Salary')
        self.assertContains(response, '95000.00')
