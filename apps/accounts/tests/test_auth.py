from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.accounts.permissions import IsAdmin, IsHR, IsOwnerOrHR, CanAccessPayroll, IsSelfOrHR


class UserModelTests(TestCase):
    """Tests for custom User model."""

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

    def test_create_user_with_email(self):
        """Test creating user with email as username."""
        user = User.objects.create_user(
            email='test@hrms.com',
            password='SecurePass123!'
        )
        self.assertEqual(user.email, 'test@hrms.com')
        self.assertTrue(user.check_password('SecurePass123!'))
        self.assertEqual(user.role, User.Role.EMPLOYEE)
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_create_superuser(self):
        """Test creating superuser with ADMIN role."""
        self.assertEqual(self.admin.role, User.Role.ADMIN)
        self.assertTrue(self.admin.is_staff)
        self.assertTrue(self.admin.is_superuser)
        self.assertTrue(self.admin.is_active)

    def test_create_user_with_role(self):
        """Test creating user with specific role."""
        hr = User.objects.create_user(
            email='hr2@hrms.com',
            password='SecurePass123!',
            role=User.Role.HR
        )
        self.assertEqual(hr.role, User.Role.HR)

    def test_get_initials(self):
        """Test get_initials method."""
        self.assertEqual(self.admin.get_initials(), 'AU')
        self.assertEqual(self.employee.get_initials(), 'EU')

    def test_get_initials_fallback(self):
        """Test get_initials falls back to email first char."""
        user = User.objects.create_user(
            email='test@hrms.com',
            password='SecurePass123!'
        )
        self.assertEqual(user.get_initials(), 'T')

    def test_get_role_display(self):
        """Test get_role_display method."""
        self.assertEqual(self.admin.get_role_display(), 'Admin')
        self.assertEqual(self.hr.get_role_display(), 'HR')
        self.assertEqual(self.employee.get_role_display(), 'Employee')

    def test_is_admin_property(self):
        """Test is_admin property."""
        self.assertTrue(self.admin.is_admin)
        self.assertFalse(self.hr.is_admin)
        self.assertFalse(self.employee.is_admin)

    def test_is_hr_property(self):
        """Test is_hr property."""
        self.assertTrue(self.admin.is_hr)
        self.assertTrue(self.hr.is_hr)
        self.assertFalse(self.employee.is_hr)

    def test_is_employee_property(self):
        """Test is_employee property."""
        self.assertFalse(self.admin.is_employee)
        self.assertFalse(self.hr.is_employee)
        self.assertTrue(self.employee.is_employee)

    def test_can_access_payroll(self):
        """Test can_access_payroll method."""
        self.assertTrue(self.admin.can_access_payroll())
        self.assertTrue(self.hr.can_access_payroll())
        self.assertFalse(self.employee.can_access_payroll())

    def test_can_manage_users(self):
        """Test can_manage_users method."""
        self.assertTrue(self.admin.can_manage_users())
        self.assertFalse(self.hr.can_manage_users())
        self.assertFalse(self.employee.can_manage_users())

    def test_email_unique(self):
        """Test email uniqueness constraint."""
        with self.assertRaises(Exception):
            User.objects.create_user(
                email='admin@hrms.com',
                password='SecurePass123!'
            )

    def test_employee_id_unique(self):
        """Test employee_id uniqueness constraint."""
        User.objects.create_user(
            email='emp1@hrms.com',
            password='SecurePass123!',
            employee_id='EMP001'
        )
        with self.assertRaises(Exception):
            User.objects.create_user(
                email='emp2@hrms.com',
                password='SecurePass123!',
                employee_id='EMP001'
            )


class AuthViewTests(TestCase):
    """Tests for authentication views."""

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

    def test_login_page_accessible(self):
        """Test login page is accessible."""
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 200)

    def test_login_redirect_authenticated_user(self):
        """Test authenticated user is redirected from login."""
        self.client.force_login(self.employee)
        response = self.client.get(reverse('accounts:login'))
        self.assertEqual(response.status_code, 302)

    def test_login_success_admin(self):
        """Test successful login redirects admin to admin dashboard."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'admin@hrms.com',
            'password': 'SecurePass123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('admin-dashboard'))

    def test_login_success_hr(self):
        """Test successful login redirects HR to HR dashboard."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'hr@hrms.com',
            'password': 'SecurePass123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('hr-dashboard'))

    def test_login_success_employee(self):
        """Test successful login redirects employee to employee dashboard."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'emp@hrms.com',
            'password': 'SecurePass123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('my-dashboard'))

    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'admin@hrms.com',
            'password': 'WrongPassword123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid email or password')

    def test_login_inactive_user(self):
        """Test login with inactive user - shows generic error (no info leak)."""
        self.employee.is_active = False
        self.employee.save()
        response = self.client.post(reverse('accounts:login'), {
            'email': 'emp@hrms.com',
            'password': 'SecurePass123!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Invalid email or password')

    def test_logout(self):
        """Test logout view."""
        self.client.force_login(self.employee)
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('accounts:login'))

    def test_dashboard_redirect_admin(self):
        """Test dashboard redirect for admin."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('accounts:dashboard_redirect'))
        self.assertRedirects(response, reverse('admin-dashboard'))

    def test_dashboard_redirect_hr(self):
        """Test dashboard redirect for HR."""
        self.client.force_login(self.hr)
        response = self.client.get(reverse('accounts:dashboard_redirect'))
        self.assertRedirects(response, reverse('hr-dashboard'))

    def test_dashboard_redirect_employee(self):
        """Test dashboard redirect for employee."""
        self.client.force_login(self.employee)
        response = self.client.get(reverse('accounts:dashboard_redirect'))
        self.assertRedirects(response, reverse('my-dashboard'))

    def test_password_change_view(self):
        """Test password change view."""
        self.client.force_login(self.employee)
        response = self.client.get(reverse('accounts:password_change'))
        self.assertEqual(response.status_code, 200)

    def test_password_change_success(self):
        """Test successful password change."""
        self.client.force_login(self.employee)
        response = self.client.post(reverse('accounts:password_change'), {
            'old_password': 'SecurePass123!',
            'new_password1': 'NewSecurePass456!',
            'new_password2': 'NewSecurePass456!'
        })
        self.assertEqual(response.status_code, 302)
        self.employee.refresh_from_db()
        self.assertTrue(self.employee.check_password('NewSecurePass456!'))

    def test_password_change_fails_short_password(self):
        """Test password change fails with short password."""
        self.client.force_login(self.employee)
        response = self.client.post(reverse('accounts:password_change'), {
            'old_password': 'SecurePass123!',
            'new_password1': 'Short1!',
            'new_password2': 'Short1!'
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'at least 12 characters')


class PermissionTests(TestCase):
    """Tests for permission classes."""

    def setUp(self):
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

        self.factory = APIClient()

    def test_is_admin_permission(self):
        """Test IsAdmin permission."""
        perm = IsAdmin()

        # Admin should have permission
        request = type('Request', (), {'user': self.admin})()
        self.assertTrue(perm.has_permission(request, None))

        # HR should not have permission
        request.user = self.hr
        self.assertFalse(perm.has_permission(request, None))

        # Employee should not have permission
        request.user = self.employee
        self.assertFalse(perm.has_permission(request, None))

        # Unauthenticated should not have permission
        request.user = type('User', (), {'is_authenticated': False})()
        self.assertFalse(perm.has_permission(request, None))

    def test_is_hr_permission(self):
        """Test IsHR permission."""
        perm = IsHR()

        # Admin should have permission
        request = type('Request', (), {'user': self.admin})()
        self.assertTrue(perm.has_permission(request, None))

        # HR should have permission
        request.user = self.hr
        self.assertTrue(perm.has_permission(request, None))

        # Employee should not have permission
        request.user = self.employee
        self.assertFalse(perm.has_permission(request, None))

    def test_is_owner_or_hr_permission(self):
        """Test IsOwnerOrHR permission."""
        perm = IsOwnerOrHR()

        # Admin has object permission
        request = type('Request', (), {'user': self.admin})()
        self.assertTrue(perm.has_object_permission(request, None, self.employee))

        # HR has object permission
        request.user = self.hr
        self.assertTrue(perm.has_object_permission(request, None, self.employee))

        # Employee owns their own object
        request.user = self.employee
        self.assertTrue(perm.has_object_permission(request, None, self.employee))

        # Employee cannot access other employee's object
        self.assertFalse(perm.has_object_permission(request, None, self.employee2))

    def test_can_access_payroll_permission(self):
        """Test CanAccessPayroll permission."""
        perm = CanAccessPayroll()

        # Admin has permission
        request = type('Request', (), {'user': self.admin})()
        self.assertTrue(perm.has_permission(request, None))

        # HR has permission
        request.user = self.hr
        self.assertTrue(perm.has_permission(request, None))

        # Employee does not have permission
        request.user = self.employee
        self.assertFalse(perm.has_permission(request, None))

        # Employee cannot access other's payroll
        request.user = self.employee
        self.assertFalse(perm.has_object_permission(request, None, self.employee2))

        # Employee can access own payroll (if object has employee field)
        class MockPayroll:
            def __init__(self, user):
                self.employee = type('Emp', (), {'user': user})()

        own_payroll = MockPayroll(self.employee)
        self.assertTrue(perm.has_object_permission(request, None, own_payroll))

    def test_is_self_or_hr_permission(self):
        """Test IsSelfOrHR permission."""
        perm = IsSelfOrHR()

        # Admin has permission
        request = type('Request', (), {'user': self.admin})()
        self.assertTrue(perm.has_object_permission(request, None, self.employee))

        # HR has permission
        request.user = self.hr
        self.assertTrue(perm.has_object_permission(request, None, self.employee))

        # Employee owns their own object
        request.user = self.employee
        self.assertTrue(perm.has_object_permission(request, None, self.employee))

        # Employee cannot access other employee's object
        self.assertFalse(perm.has_object_permission(request, None, self.employee2))


class UnauthenticatedAccessTests(TestCase):
    """Tests for unauthenticated access blocking."""

    def setUp(self):
        self.client = APIClient()

    def test_login_required_for_dashboard(self):
        """Test dashboard redirect requires authentication."""
        response = self.client.get(reverse('accounts:dashboard_redirect'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_logout_requires_authentication(self):
        """Test logout requires authentication."""
        response = self.client.post(reverse('accounts:logout'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_password_change_requires_authentication(self):
        """Test password change requires authentication."""
        response = self.client.get(reverse('accounts:password_change'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    def test_api_user_info_requires_authentication(self):
        """Test API user info requires authentication - redirects to login."""
        response = self.client.get(reverse('accounts:api_user_info'))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)


class PasswordValidationTests(TestCase):
    """Tests for password validation rules."""

    def test_password_min_length(self):
        """Test password minimum length 12."""
        from django.contrib.auth.password_validation import validate_password
        with self.assertRaises(Exception):
            validate_password('Short1!A')

    def test_password_requires_uppercase(self):
        """Test password requires uppercase."""
        from django.contrib.auth.password_validation import validate_password
        with self.assertRaises(Exception):
            validate_password('lowercase123!')

    def test_password_requires_lowercase(self):
        """Test password requires lowercase."""
        from django.contrib.auth.password_validation import validate_password
        with self.assertRaises(Exception):
            validate_password('UPPERCASE123!')

    def test_password_requires_digit(self):
        """Test password requires digit."""
        from django.contrib.auth.password_validation import validate_password
        with self.assertRaises(Exception):
            validate_password('Password!')

    def test_password_requires_special_char(self):
        """Test password requires special character."""
        from django.contrib.auth.password_validation import validate_password
        with self.assertRaises(Exception):
            validate_password('Password123')

    def test_valid_password_accepted(self):
        """Test valid password is accepted."""
        user = User.objects.create_user(
            email='test@hrms.com',
            password='ValidPass123!'
        )
        self.assertTrue(user.check_password('ValidPass123!'))


class APIUserInfoTests(TestCase):
    """Tests for API user info endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.employee = User.objects.create_user(
            email='emp@hrms.com',
            password='SecurePass123!',
            first_name='John',
            last_name='Doe',
            department='Engineering',
            employee_id='EMP001',
            phone='+1234567890',
            role=User.Role.EMPLOYEE
        )

    def test_api_user_info_returns_correct_data(self):
        """Test API returns correct user info."""
        self.client.force_login(self.employee)
        response = self.client.get(reverse('accounts:api_user_info'))
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertEqual(data['email'], 'emp@hrms.com')
        self.assertEqual(data['first_name'], 'John')
        self.assertEqual(data['last_name'], 'Doe')
        self.assertEqual(data['full_name'], 'John Doe')
        self.assertEqual(data['initials'], 'JD')
        self.assertEqual(data['role'], 'EMPLOYEE')
        self.assertEqual(data['role_display'], 'Employee')
        self.assertEqual(data['department'], 'Engineering')
        self.assertEqual(data['employee_id'], 'EMP001')
        self.assertEqual(data['phone'], '+1234567890')
        self.assertFalse(data['is_admin'])
        self.assertFalse(data['is_hr'])
        self.assertTrue(data['is_employee'])
        self.assertFalse(data['can_access_payroll'])
        self.assertFalse(data['can_manage_users'])