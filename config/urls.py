
"""
URL configuration for the Smart HRMS project.
"""
from functools import wraps

from django.contrib import admin
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render
from django.urls import include, path, reverse

from apps.accounts.models import User
from apps.employees.models import Department, Employee


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role not in allowed_roles:
                return HttpResponseForbidden(
                    "You do not have permission to access this page."
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def get_dashboard_context(request, title, menu_items, cards):
    return {
        "user": request.user,
        "role": request.user.get_role_display(),
        "dashboard_title": title,
        "menu_items": menu_items,
        "cards": cards,
    }


@login_required
@role_required(User.Role.ADMIN)
def admin_dashboard(request):
    menu_items = [
        {
            "label": "Dashboard",
            "url": reverse("admin-dashboard"),
            "icon": "⌂",
            "active": True,
        },
        {
            "label": "Django Admin",
            "url": reverse("admin:index"),
            "icon": "⚙",
            "active": False,
        },
    ]

    cards = [
        {
            "title": "Total User Accounts",
            "value": User.objects.count(),
            "icon": "👥",
        },
        {
            "title": "Active Employees",
            "value": Employee.objects.filter(
                employment_status=Employee.EmploymentStatus.ACTIVE
            ).count(),
            "icon": "✓",
        },
        {
            "title": "Departments",
            "value": Department.objects.filter(is_active=True).count(),
            "icon": "▤",
        },
    ]

    context = get_dashboard_context(
        request, "Admin Dashboard", menu_items, cards
    )
    return render(request, "dashboards/admin_dashboard.html", context)


@login_required
@role_required(User.Role.ADMIN, User.Role.HR)
def hr_dashboard(request):
    menu_items = [
        {
            "label": "Dashboard",
            "url": reverse("hr-dashboard"),
            "icon": "⌂",
            "active": True,
        },
        {
            "label": "My Profile",
            "url": reverse("accounts:profile"),
            "icon": "👤",
            "active": False,
        },
    ]

    cards = [
        {
            "title": "Employee Profiles",
            "value": Employee.objects.count(),
            "icon": "👥",
        },
        {
            "title": "Active Employees",
            "value": Employee.objects.filter(
                employment_status=Employee.EmploymentStatus.ACTIVE
            ).count(),
            "icon": "✓",
        },
        {
            "title": "Departments",
            "value": Department.objects.filter(is_active=True).count(),
            "icon": "▤",
        },
    ]

    context = get_dashboard_context(
        request, "HR Dashboard", menu_items, cards
    )
    return render(request, "dashboards/hr_dashboard.html", context)


@login_required
def my_dashboard(request):
    menu_items = [
        {
            "label": "Dashboard",
            "url": reverse("my-dashboard"),
            "icon": "⌂",
            "active": True,
        },
        {
            "label": "My Profile",
            "url": reverse("accounts:profile"),
            "icon": "👤",
            "active": False,
        },
        {
            "label": "Change Password",
            "url": reverse("accounts:password_change"),
            "icon": "🔒",
            "active": False,
        },
    ]

    cards = [
        {
            "title": "Leave Balance",
            "value": "Not configured",
            "icon": "▦",
        },
        {
            "title": "Attendance",
            "value": "Not configured",
            "icon": "◷",
        },
        {
            "title": "Pending Requests",
            "value": "Not configured",
            "icon": "…",
        },
    ]

    context = get_dashboard_context(
        request, "My Dashboard", menu_items, cards
    )
    return render(request, "dashboards/employee_dashboard.html", context)


urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "accounts/",
        include("apps.accounts.urls", namespace="accounts"),
    ),
    path("admin-dashboard/", admin_dashboard, name="admin-dashboard"),
    path("hr-dashboard/", hr_dashboard, name="hr-dashboard"),
    path("my-dashboard/", my_dashboard, name="my-dashboard"),
    path("", lambda request: redirect("accounts:login")),
]
