from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .forms import DepartmentForm, EmployeeForm
from .models import Department, Employee

User = get_user_model()


def role_required(*allowed_roles):
    """
    Decorator ensuring the authenticated user has one of the allowed roles.
    Renders 'errors/403.html' with HTTP 403 if unauthorized, or redirects
    unauthenticated requests to LOGIN_URL.
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                login_url = getattr(settings, 'LOGIN_URL', 'accounts:login')
                try:
                    resolved_url = reverse(login_url)
                except NoReverseMatch:
                    resolved_url = '/accounts/login/'
                return redirect(f"{resolved_url}?next={request.path}")
            if request.user.role not in allowed_roles:
                return render(
                    request,
                    "errors/403.html",
                    status=403,
                )
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def _get_menu_items(request, active_label=""):
    """Build sidebar navigation items with proper active state."""
    try:
        if request.user.role == User.Role.ADMIN:
            dashboard_url = reverse("admin-dashboard")
        elif request.user.role == User.Role.HR:
            dashboard_url = reverse("hr-dashboard")
        else:
            dashboard_url = reverse("my-dashboard")
    except NoReverseMatch:
        dashboard_url = "/accounts/dashboard/"

    try:
        emp_list_url = reverse("employees:employee_list")
    except NoReverseMatch:
        emp_list_url = "/employees/"

    try:
        dept_list_url = reverse("employees:department_list")
    except NoReverseMatch:
        dept_list_url = "/employees/departments/"

    try:
        profile_url = reverse("accounts:profile")
    except NoReverseMatch:
        profile_url = "/accounts/profile/"

    return [
        {
            "label": "Dashboard",
            "url": dashboard_url,
            "icon": "⌂",
            "active": active_label == "Dashboard",
        },
        {
            "label": "Employees",
            "url": emp_list_url,
            "icon": "👥",
            "active": active_label == "Employees",
        },
        {
            "label": "Departments",
            "url": dept_list_url,
            "icon": "▤",
            "active": active_label == "Departments",
        },
        {
            "label": "My Profile",
            "url": profile_url,
            "icon": "👤",
            "active": active_label == "Profile",
        },
    ]


# ==============================================================================
# Employee Views
# ==============================================================================

@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET'])
def employee_list(request):
    """
    Employee directory listing with search, filtering, and pagination.
    Restricted to ADMIN and HR roles.
    """
    employees = Employee.objects.select_related(
        'department', 'job_title', 'user'
    ).all().order_by('full_name')

    # Search by full_name, email, or employee_id (case-insensitive)
    query = request.GET.get('q', '').strip()
    if not query:
        query = request.GET.get('search', '').strip()

    if query:
        employees = employees.filter(
            Q(full_name__icontains=query) |
            Q(email__icontains=query) |
            Q(employee_id__icontains=query)
        )

    # Filter by department (ID or name)
    dept_param = request.GET.get('department', '').strip()
    if dept_param:
        if dept_param.isdigit():
            employees = employees.filter(department_id=int(dept_param))
        else:
            employees = employees.filter(department__name__iexact=dept_param)

    # Filter by employment status
    status_param = request.GET.get('employment_status', '').strip()
    if not status_param:
        status_param = request.GET.get('status', '').strip()

    if status_param:
        status_param = status_param.upper()
        employees = employees.filter(employment_status=status_param)

    # Pagination: 10 per page
    paginator = Paginator(employees, 10)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    # Preserve search and filter query parameters across pagination links
    query_params = request.GET.copy()
    if 'page' in query_params:
        query_params.pop('page')
    pagination_query_string = query_params.urlencode()

    departments = Department.objects.all().order_by('name')
    menu_items = _get_menu_items(request, active_label='Employees')

    context = {
        'page_obj': page_obj,
        'employees': page_obj.object_list,
        'paginator': paginator,
        'is_paginated': page_obj.has_other_pages(),
        'search_query': query,
        'selected_department': dept_param,
        'selected_status': status_param,
        'departments': departments,
        'status_choices': Employee.EmploymentStatus.choices,
        'pagination_query_string': pagination_query_string,
        'menu_items': menu_items,
    }
    return render(request, 'employees/employee_list.html', context)


@login_required
@require_http_methods(['GET'])
def employee_detail(request, pk):
    """
    Employee detail view.
    - ADMIN and HR can view any employee.
    - EMPLOYEE can view only their own linked profile.
    - All other unauthorized access attempts return 403.
    """
    employee = get_object_or_404(
        Employee.objects.select_related('department', 'job_title', 'user'),
        pk=pk
    )

    # Access control: HR/Admin or self
    is_admin_or_hr = request.user.role in (User.Role.ADMIN, User.Role.HR)
    is_self = (employee.user_id == request.user.pk)

    if not (is_admin_or_hr or is_self):
        return render(
            request,
            "errors/403.html",
            status=403,
        )

    completeness = employee.calculate_profile_completeness()
    menu_items = _get_menu_items(
        request,
        active_label='Profile' if is_self and not is_admin_or_hr else 'Employees'
    )

    context = {
        'employee': employee,
        'profile_completeness': completeness,
        'completeness': completeness,
        'is_self': is_self,
        'is_admin_or_hr': is_admin_or_hr,
        'menu_items': menu_items,
    }
    return render(request, 'employees/employee_detail.html', context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET', 'POST'])
def employee_create(request):
    """
    Employee creation view. Restricted to ADMIN and HR.
    Saves new employee with audit actor context.
    """
    if request.method == 'POST':
        form = EmployeeForm(request.POST)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.save(audit_actor=request.user, audit_request=request)
            form.save_m2m()

            messages.success(
                request,
                _('Employee "%(name)s" (%(id)s) was successfully created.') % {
                    'name': employee.full_name,
                    'id': employee.employee_id,
                }
            )

            try:
                return redirect('employees:employee_detail', pk=employee.pk)
            except NoReverseMatch:
                try:
                    return redirect('employees:detail', pk=employee.pk)
                except NoReverseMatch:
                    return redirect(f'/employees/{employee.pk}/')
    else:
        form = EmployeeForm()

    menu_items = _get_menu_items(request, active_label='Employees')

    context = {
        'form': form,
        'action': 'create',
        'title': _('Add Employee'),
        'menu_items': menu_items,
    }
    return render(request, 'employees/employee_form.html', context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET', 'POST'])
def employee_edit(request, pk):
    """
    Employee edit view. Restricted to ADMIN and HR.
    Updates employee with audit actor context.
    """
    employee = get_object_or_404(Employee, pk=pk)

    if request.method == 'POST':
        form = EmployeeForm(request.POST, instance=employee)
        if form.is_valid():
            employee = form.save(commit=False)
            employee.save(audit_actor=request.user, audit_request=request)
            form.save_m2m()

            messages.success(
                request,
                _('Employee "%(name)s" (%(id)s) was successfully updated.') % {
                    'name': employee.full_name,
                    'id': employee.employee_id,
                }
            )

            try:
                return redirect('employees:employee_detail', pk=employee.pk)
            except NoReverseMatch:
                try:
                    return redirect('employees:detail', pk=employee.pk)
                except NoReverseMatch:
                    return redirect(f'/employees/{employee.pk}/')
    else:
        form = EmployeeForm(instance=employee)

    menu_items = _get_menu_items(request, active_label='Employees')

    context = {
        'form': form,
        'employee': employee,
        'action': 'edit',
        'title': _('Edit Employee'),
        'menu_items': menu_items,
    }
    return render(request, 'employees/employee_form.html', context)


# ==============================================================================
# Department Views
# ==============================================================================

@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET'])
def department_list(request):
    """
    Department directory listing with assigned employee count annotations.
    Restricted to ADMIN and HR.
    """
    departments = Department.objects.select_related(
        'department_head'
    ).annotate(
        employee_count=Count('employees')
    ).order_by('name')

    menu_items = _get_menu_items(request, active_label='Departments')

    context = {
        'departments': departments,
        'menu_items': menu_items,
    }
    return render(request, 'employees/department_list.html', context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET', 'POST'])
def department_create(request):
    """
    Department creation view. Restricted to ADMIN and HR.
    """
    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            department = form.save(commit=False)
            department.save(audit_actor=request.user, audit_request=request)
            form.save_m2m()

            messages.success(
                request,
                _('Department "%(name)s" was successfully created.') % {
                    'name': department.name,
                }
            )
            return redirect('employees:department_list')
    else:
        form = DepartmentForm()

    menu_items = _get_menu_items(request, active_label='Departments')

    context = {
        'form': form,
        'action': 'create',
        'title': _('Add Department'),
        'menu_items': menu_items,
    }
    return render(request, 'employees/department_form.html', context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET', 'POST'])
def department_edit(request, pk):
    """
    Department edit view. Restricted to ADMIN and HR.
    """
    department = get_object_or_404(Department, pk=pk)

    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=department)
        if form.is_valid():
            department = form.save(commit=False)
            department.save(audit_actor=request.user, audit_request=request)
            form.save_m2m()

            messages.success(
                request,
                _('Department "%(name)s" was successfully updated.') % {
                    'name': department.name,
                }
            )
            return redirect('employees:department_list')
    else:
        form = DepartmentForm(instance=department)

    menu_items = _get_menu_items(request, active_label='Departments')

    context = {
        'form': form,
        'department': department,
        'action': 'edit',
        'title': _('Edit Department'),
        'menu_items': menu_items,
    }
    return render(request, 'employees/department_form.html', context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET', 'POST'])
def department_delete(request, pk):
    """
    Department deletion confirmation and execution view. Restricted to ADMIN and HR.
    Never deletes on GET.
    Prevents deletion if assigned employees exist, catching ProtectedError safely.
    """
    department = get_object_or_404(
        Department.objects.annotate(employee_count=Count('employees')),
        pk=pk
    )

    if request.method == 'POST':
        # Check if employees are currently assigned to this department
        if department.employee_count > 0 or department.employees.exists():
            messages.error(
                request,
                _(
                    'Cannot delete department "%(name)s" because it has '
                    '%(count)d assigned employee(s). Please reassign them first.'
                ) % {
                    'name': department.name,
                    'count': department.employee_count,
                }
            )
            return redirect('employees:department_list')

        try:
            dept_name = department.name
            department.delete(audit_actor=request.user, audit_request=request)
            messages.success(
                request,
                _('Department "%(name)s" was successfully deleted.') % {
                    'name': dept_name,
                }
            )
        except ProtectedError:
            messages.error(
                request,
                _(
                    'Cannot delete department "%(name)s" because other records '
                    'depend on it.'
                ) % {'name': department.name}
            )
        return redirect('employees:department_list')

    menu_items = _get_menu_items(request, active_label='Departments')

    context = {
        'department': department,
        'has_assigned_employees': (department.employee_count > 0 or department.employees.exists()),
        'menu_items': menu_items,
    }
    return render(request, 'employees/department_confirm_delete.html', context)
