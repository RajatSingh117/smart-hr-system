"""
URL configuration for the Smart HRMS project.
"""

from functools import wraps

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import include, path, reverse

from apps.accounts.models import User
from apps.employees.models import Department, Employee


from apps.reports.navigation import menu_for_role
from apps.reports.views import (
    ADMIN_CARDS,
    HR_CARDS,
    EMPLOYEE_CARDS,
    org_card_values,
)


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.role not in allowed_roles:
                return render(
                    request,
                    "errors/403.html",
                    status=403,
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_dashboard_context(request, title, role_str, menu_items, cards):
    return {
        "user": request.user,
        "role": role_str,
        "dashboard_title": title,
        "menu_items": menu_items,
        "cards": cards,
    }


@login_required
@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    values = org_card_values()
    cards = [
        {**card, "value": values.get(card["title"], card["value"])}
        for card in ADMIN_CARDS
    ]
    menu_items = menu_for_role("admin", request.path, valid_only=True)
    from apps.accounts.models import AuditEvent
    recent_events = AuditEvent.objects.select_related('actor').order_by('-timestamp')[:5]
    context = get_dashboard_context(
        request, "Admin Dashboard", "admin", menu_items, cards
    )
    context["recent_events"] = recent_events
    return render(request, "dashboards/admin_dashboard.html", context)


@login_required
@role_required(User.Role.ADMIN, User.Role.HR)
def hr_dashboard(request):
    values = org_card_values()
    cards = [
        {**card, "value": values.get(card["title"], card["value"])}
        for card in HR_CARDS
    ]
    user_role = getattr(request.user, "role", None)
    role_str = "admin" if (request.user.is_superuser or user_role == User.Role.ADMIN) else "hr"
    menu_items = menu_for_role(role_str, request.path, valid_only=True)
    from apps.employees.models import Department
    from django.db.models import Count
    top_departments = Department.objects.filter(is_active=True).annotate(
        emp_count=Count('employees')
    ).order_by('-emp_count')[:5]
    context = get_dashboard_context(
        request, "HR Dashboard", role_str, menu_items, cards
    )
    context["top_departments"] = top_departments
    return render(request, "dashboards/hr_dashboard.html", context)


@login_required
def my_dashboard(request):
    user = request.user
    user_role = getattr(user, "role", None)
    role_str = (
        "admin"
        if (user.is_superuser or user_role == User.Role.ADMIN)
        else ("hr" if user_role == User.Role.HR else "employee")
    )
    menu_items = menu_for_role(role_str, request.path, valid_only=True)
    emp = Employee.objects.filter(user=user).first()

    emp_values = {}
    recent_leaves = []
    if emp:
        from apps.attendance.models import Attendance
        from apps.leave_management.models import LeaveRequest
        from apps.leave_management.aggregates import get_employee_leave_dashboard
        from django.utils import timezone
        today = timezone.localdate()

        my_att_count = Attendance.objects.filter(
            employee=emp, date__year=today.year, date__month=today.month, status='PRESENT'
        ).count()
        emp_values["My Attendance This Month"] = f"{my_att_count} days"

        pending_count = LeaveRequest.objects.filter(employee=emp, status='PENDING').count()
        emp_values["My Pending Leave"] = pending_count

        try:
            dashboard = get_employee_leave_dashboard(emp, today.year)
            rem_days = sum(item["remaining_days"] for item in dashboard.get("balances", []))
            emp_values["My Leave Balance"] = f"{rem_days} days"
        except Exception:
            emp_values["My Leave Balance"] = "--"

        recent_leaves = LeaveRequest.objects.filter(employee=emp).select_related('leave_type').order_by('-created_at')[:5]

    cards = [
        {**card, "value": emp_values.get(card["title"], card["value"])}
        for card in EMPLOYEE_CARDS
    ]
    context = get_dashboard_context(
        request, "My Dashboard", role_str, menu_items, cards
    )
    context["my_employee"] = emp
    context["recent_leaves"] = recent_leaves
    return render(
        request,
        "dashboards/employee_dashboard.html",
        context,
    )


urlpatterns = [
    path("admin/", admin.site.urls),

    path(
        "accounts/",
        include("apps.accounts.urls", namespace="accounts"),
    ),

    path(
        "employees/",
        include("apps.employees.urls", namespace="employees"),
    ),

    path(
        "admin-dashboard/",
        admin_dashboard,
        name="admin-dashboard",
    ),

    path(
        "hr-dashboard/",
        hr_dashboard,
        name="hr-dashboard",
    ),

    path(
        "my-dashboard/",
        my_dashboard,
        name="my-dashboard",
    ),

    path(
        "reports/",
        include("apps.reports.urls", namespace="reports"),
    ),

    # Attendance and leave pages
    path(
        "attendance/",
        include("apps.attendance.urls", namespace="attendance"),
    ),

    path(
        "leave/",
        include("apps.leave_management.urls", namespace="leave_management"),
    ),

    # Existing payroll web URLs
    path(
        "payroll/",
        include("apps.payroll.urls", namespace="payroll"),
    ),

    # Payroll API URLs
    path(
        "api/payroll/",
        include("apps.payroll.api_urls"),
    ),

    # Default redirect
    path(
        "",
        lambda request: redirect("accounts:login"),
    ),
]
