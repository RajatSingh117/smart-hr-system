from rest_framework import permissions
from apps.accounts.models import User


class IsAdmin(permissions.BasePermission):
    """
    Allows access only to users with ADMIN role.
    """

    message = 'Only administrators can access this resource.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role == User.Role.ADMIN
        )


class IsHR(permissions.BasePermission):
    """
    Allows access to users with ADMIN or HR role.
    """

    message = 'Only HR or Admin users can access this resource.'
    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [User.Role.ADMIN, User.Role.HR]
        )


class IsOwnerOrHR(permissions.BasePermission):
    """
    Allows access to object owner, HR, or Admin.
    For employee self-service: users can only access their own records.
    """

    message = 'You do not have permission to access this resource.'

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        # Admin and HR can access everything
        if request.user.role in [User.Role.ADMIN, User.Role.HR]:
            return True

        # Employee can only access their own records
        if hasattr(obj, 'user'):
            return obj.user == request.user

        if hasattr(obj, 'employee'):
            return obj.employee.user == request.user

        if isinstance(obj, User):
            return obj == request.user

        return False


class CanAccessPayroll(permissions.BasePermission):
    """
    Allows HR and Admin to access payroll generally.
    Employees can access only their own payroll objects
    through object-level permission checks.
    """

    message = 'Payroll access is restricted to HR and Admin users.'

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in [User.Role.ADMIN, User.Role.HR]
        )

    def has_object_permission(self, request, view, obj):
        # Admin and HR can access all payroll records
        if request.user.role in [User.Role.ADMIN, User.Role.HR]:
            return True

        # Check Payslip ownership
        if hasattr(obj, 'payroll_record'):
            return obj.payroll_record.employee.user == request.user

        # Check PayrollRecord ownership
        if hasattr(obj, 'employee'):
            return obj.employee.user == request.user

        # Check direct user ownership
        if hasattr(obj, 'user'):
            return obj.user == request.user

        return False


class IsSelfOrHR(permissions.BasePermission):
    """
    Allows access to own data or HR/Admin.
    Used for profile, attendance, leave views.
    """

    message = 'You can only access your own data.'

    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated

    def has_object_permission(self, request, view, obj):
        if request.user.role in [User.Role.ADMIN, User.Role.HR]:
            return True

        # Check ownership through various relationships
        if hasattr(obj, 'user'):
            return obj.user == request.user

        if hasattr(obj, 'employee'):
            return obj.employee.user == request.user

        if isinstance(obj, User):
            return obj == request.user

        return False