"""Role checks for the reports app. Roles: admin, hr, employee."""
from django.contrib.auth.mixins import UserPassesTestMixin

from apps.employees.models import Employee

HR_ROLES = ("admin", "hr")


def user_role(user):
    return str(getattr(user, "role", "") or "").lower()

def is_hr_or_admin(user):
    return user.is_authenticated and (
        user.is_superuser or user_role(user) in HR_ROLES
    )


def employee_for(user):
    """Return the Employee row that belongs to this user, or None."""
    if not user.is_authenticated:
        return None
    field_names = {f.name for f in Employee._meta.get_fields()}
    if "user" in field_names:
        employee = Employee.objects.filter(user=user).first()
        if employee:
            return employee
    if getattr(user, "email", ""):
        return Employee.objects.filter(email__iexact=user.email).first()
    return None


class RoleRequiredMixin(UserPassesTestMixin):
    """Anonymous -> login page. Wrong role -> 403."""

    allowed_roles = HR_ROLES

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (
            user.is_superuser or user_role(user) in self.allowed_roles
        )