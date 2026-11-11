from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Sum
from django.shortcuts import redirect, render
from django.views import View
from django.views.decorators.http import require_GET
from django.views.generic import TemplateView

from apps.accounts.models import User
from apps.employees.models import Department, Employee
from apps.payroll.models import (
    NotificationLog,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
)

from .navigation import ADMIN, EMPLOYEE, HR, menu_for_role


ROLE_TO_URL_NAME = {
    ADMIN: "reports:admin_dashboard",
    HR: "reports:hr_dashboard",
    EMPLOYEE: "reports:employee_dashboard",
}


def get_role(user):
    """Read the role from the custom User model."""
    return getattr(user, "role", None)


class DashboardRedirectView(LoginRequiredMixin, View):
    """Redirect users to their role-specific dashboard."""

    def get(self, request):
        url_name = ROLE_TO_URL_NAME.get(get_role(request.user))

        if url_name is None:
            raise PermissionDenied("Your account has no valid role.")

        return redirect(url_name)


class RoleDashboardView(LoginRequiredMixin, TemplateView):
    """Base class for role-specific dashboards."""

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
            self.required_role,
            self.request.path,
        )
        context["cards"] = self.cards

        return context


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


def get_payroll_period_summaries():
    """Return payroll totals grouped by payroll period."""

    summaries = []

    periods = PayrollPeriod.objects.all().order_by("-start_date")

    for period in periods:
        totals = PayrollRecord.objects.filter(
            payroll_period=period
        ).aggregate(
            total_records=Count("id"),
            total_basic_salary=Sum("basic_salary"),
            total_allowances=Sum("total_allowances"),
            total_deductions=Sum("total_deductions"),
            total_gross_salary=Sum("gross_salary"),
            total_net_salary=Sum("net_salary"),
        )

        summaries.append({
            "period": period,
            "total_records": totals["total_records"],
            "total_basic_salary": totals["total_basic_salary"] or 0,
            "total_allowances": totals["total_allowances"] or 0,
            "total_deductions": totals["total_deductions"] or 0,
            "total_gross_salary": totals["total_gross_salary"] or 0,
            "total_net_salary": totals["total_net_salary"] or 0,
        })

    return summaries


def get_payslip_generation_metrics():
    """Return payslip generation statistics."""

    total_payslips = Payslip.objects.count()

    generated_payslips = Payslip.objects.filter(
        status=Payslip.Status.GENERATED
    ).count()

    failed_payslips = Payslip.objects.filter(
        status=Payslip.Status.FAILED
    ).count()

    success_rate = (
        (generated_payslips / total_payslips) * 100
        if total_payslips > 0
        else 0
    )

    return {
        "total_payslips": total_payslips,
        "generated_payslips": generated_payslips,
        "failed_payslips": failed_payslips,
        "payslip_success_rate": round(success_rate, 2),
    }


def get_payslip_email_metrics():
    """Return payslip email notification statistics."""

    payslip_emails = NotificationLog.objects.filter(
        notification_type=NotificationLog.NotificationType.PAYSLIP_READY
    )

    total_emails = payslip_emails.count()

    sent_emails = payslip_emails.filter(
        status=NotificationLog.Status.SENT
    ).count()

    failed_emails = payslip_emails.filter(
        status=NotificationLog.Status.FAILED
    ).count()

    processed_emails = sent_emails + failed_emails

    success_rate = (
        (sent_emails / processed_emails) * 100
        if processed_emails > 0
        else 0
    )

    failure_rate = (
        (failed_emails / processed_emails) * 100
        if processed_emails > 0
        else 0
    )

    return {
        "total_emails": total_emails,
        "sent_emails": sent_emails,
        "failed_emails": failed_emails,
        "email_success_rate": round(success_rate, 2),
        "email_failure_rate": round(failure_rate, 2),
    }


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
        "payroll_period_summaries": get_payroll_period_summaries(),
        "payslip_metrics": get_payslip_generation_metrics(),
        "email_metrics": get_payslip_email_metrics(),
    }

    return render(request, "reports/dashboard.html", context)