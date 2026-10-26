
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.accounts.models import User
from apps.employees.models import Department, Employee


@login_required
@require_GET
def reports_dashboard(request):
    """Display organization-level reports to authorized staff."""

    if request.user.role not in (User.Role.ADMIN, User.Role.HR):
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
        "department_summary": (
            Department.objects.annotate(
                employee_count=Count("employees")
            ).order_by("name")
        ),
    }

    return render(request, "reports/dashboard.html", context)
