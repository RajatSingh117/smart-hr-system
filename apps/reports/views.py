from django.shortcuts import render

# Create your views here.

from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.views import View
from django.views.generic import TemplateView

from .navigation import ADMIN, EMPLOYEE, HR, menu_for_role

ROLE_TO_URL_NAME = {
    ADMIN: "reports:admin_dashboard",
    HR: "reports:hr_dashboard",
    EMPLOYEE: "reports:employee_dashboard",
}


def get_role(user):
    """Read the role from M2's custom User model (`role` field)."""
    return getattr(user, "role", None)


class DashboardRedirectView(LoginRequiredMixin, View):
    """/dashboard/ sends the logged-in user to their own dashboard."""

    def get(self, request):
        url_name = ROLE_TO_URL_NAME.get(get_role(request.user))
        if url_name is None:
            raise PermissionDenied("Your account has no valid role.")
        return redirect(url_name)


class RoleDashboardView(LoginRequiredMixin, TemplateView):
    """Base for the three dashboards. Wrong role gets the 403 page."""

    required_role = None
    cards = []

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and get_role(request.user) != self.required_role:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["role"] = self.required_role
        context["menu_items"] = menu_for_role(self.required_role, self.request.path)
        context["cards"] = self.cards
        return context


# Placeholder cards. Week 4 swaps "--" for real values from M3, M4 and M5 queries.
ADMIN_CARDS = [
    {"title": "Total Headcount", "value": "--", "icon": "👥"},
    {"title": "Departments", "value": "--", "icon": "🏢"},
    {"title": "Pending Leave Requests", "value": "--", "icon": "🌴"},
    {"title": "Latest Payroll Period", "value": "--", "icon": "💰"},
    {"title": "Recent Audit Events", "value": "--", "icon": "🛡️"},
]

HR_CARDS = [
    {"title": "Headcount", "value": "--", "icon": "👥"},
    {"title": "Pending Leave Requests", "value": "--", "icon": "🌴"},
    {"title": "Today's Attendance", "value": "--", "icon": "✅"},
    {"title": "Incomplete Profiles", "value": "--", "icon": "⚠️"},
    {"title": "Payroll Status", "value": "--", "icon": "💰"},
]

EMPLOYEE_CARDS = [
    {"title": "My Attendance This Month", "value": "--", "icon": "✅"},
    {"title": "My Leave Balance", "value": "--", "icon": "🗓️"},
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