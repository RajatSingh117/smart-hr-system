
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.accounts.models import User
from apps.employees.models import Department, Employee

from .navigation import ADMIN, EMPLOYEE, HR, menu_for_role


ROLE_TO_URL_NAME = {
    ADMIN: "reports:admin_dashboard",
    HR: "reports:hr_dashboard",
    EMPLOYEE: "reports:employee_dashboard",
}


def get_role(user):
    """Return the user's role."""
    return getattr(user, "role", None)


class DashboardRedirectView(LoginRequiredMixin, View):
    """Redirect each logged-in user to their role-specific dashboard."""

    def get(self, request):
        url_name = ROLE_TO_URL_NAME.get(get_role(request.user))
        if url_name is None:
            raise PermissionDenied("Your account has no valid role.")
        return redirect(url_name)


class RoleDashboardView(LoginRequiredMixin, TemplateView):
    """Base view for dashboards with role-based access control."""

    required_role = None
    cards = []

    def dispatch(self, request, *args, **kwargs):
        if (
            request.user.is_authenticated
            and get_role(request.user) != self.required_role
        ):
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role"] = self.required_role
        context["menu_items"] = menu_for_role(
            self.required_role, self.request.path
        )
        context["cards"] = self.cards
        return context


ADMIN_CARDS = [
    {"title": "Total Headcount", "value": "--", "icon": "👥"},
    {"title": "Departments", "value": "--", "icon": "🏢"},
    {"title": "Pending Leave Requests", "value": "--", "icon": "🌴"},
    {"title": "Latest Payroll Period", "value": "--", "icon": "💰"},
    {"title": "Recent Audit Events", "value": "--", "icon": "🛡"},
]

HR_CARDS = [
    {"title": "Headcount", "value": "--", "icon": "👥"},
    {"title": "Pending Leave Requests", "value": "--", "icon": "🌴"},
    {"title": "Today's Attendance", "value": "--", "icon": "✅"},
    {"title": "Incomplete Profiles", "value": "--", "icon": "⚠"},
    {"title": "Payroll Status", "value": "--", "icon": "💰"},
]

EMPLOYEE_CARDS = [
    {"title": "My Attendance This Month", "value": "--", "icon": "✅"},
    {"title": "My Leave Balance", "value": "--", "icon": "🗓"},
    {"title": "My Pending Leave", "value": "--", "icon": "⏳"},
    {"title": "Latest Payslip", "value": "--", "icon": "📄"},
]


class AdminDashboardView(RoleDashboardView):
    template_name = "dashboards/admin_dashboard.html"
    required_role = ADMIN
    cards = ADMIN_CARDS


class HRDashboardView(RoleDashboardView):
    template_name = "dashboards/hr_dashboard.html"
    required_role = HR
    cards = HR_CARDS


class EmployeeDashboardView(RoleDashboardView):
    template_name = "dashboards/employee_dashboard.html"
    required_role = EMPLOYEE
    cards = EMPLOYEE_CARDS


@login_required
@require_GET
def reports_dashboard(request):
    """Show organization reports to Admin and HR users only."""

    if get_role(request.user) not in (User.Role.ADMIN, User.Role.HR):
        return render(request, "errors/403.html", status=403)

    context = {
        "total_employees": Employee.objects.count(),
        "active_employees": Employee.objects.filter(
            employment_status=Employee.EmploymentStatus.ACTIVE
        ).count(),
        "employees_on_leave": Employee.objects.filter(
            employment_status=Employee.EmploymentStatus.ON_LEAVE
        ).count(),
        "terminated_employees": Employee.objects.filter(
            employment_status=Employee.EmploymentStatus.TERMINATED
        ).count(),
        "total_departments": Department.objects.count(),
        "active_departments": Department.objects.filter(
            is_active=True
        ).count(),
        "department_summary": Department.objects.annotate(
            employee_count=Count("employees")
        ).order_by("name"),
    }

    return render(request, "reports/dashboard.html", context)
