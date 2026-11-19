from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Count, ProtectedError, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import NoReverseMatch, reverse
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_http_methods

from .forms import DepartmentForm, EmployeeForm, JobTitleForm
from .models import Department, Employee, JobTitle
from .queries import get_dashboard_analytics

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
    from apps.reports.navigation import menu_for_role
    items = menu_for_role(getattr(request.user, "role", None), request.path, valid_only=True)
    if active_label:
        for item in items:
            item["active"] = (item["label"] == active_label)
    return items


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


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET'])
def employee_analytics_api(request):
    """
    JSON API endpoint providing employee headcount, department distribution,
    status breakdown, and Chart.js formatted data for dashboard integrations.
    Restricted to ADMIN and HR roles.
    """
    data = get_dashboard_analytics()
    return JsonResponse(data, safe=False)


# ==============================================================================
# Job Title Views
# ==============================================================================

@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET'])
def job_title_list(request):
    """
    Job title directory listing with employee count annotations.
    Restricted to ADMIN and HR.
    """
    job_titles = JobTitle.objects.annotate(
        employee_count=Count('employees')
    ).order_by('title')

    menu_items = _get_menu_items(request, active_label='Job Titles')

    context = {
        'job_titles': job_titles,
        'menu_items': menu_items,
    }
    return render(request, 'employees/job_title_list.html', context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET', 'POST'])
def job_title_create(request):
    """
    Job title creation view. Restricted to ADMIN and HR.
    """
    if request.method == 'POST':
        form = JobTitleForm(request.POST)
        if form.is_valid():
            job_title = form.save(commit=False)
            job_title.save(audit_actor=request.user, audit_request=request)
            form.save_m2m()

            messages.success(
                request,
                _('Job title "%(title)s" was successfully created.') % {
                    'title': job_title.title,
                }
            )
            return redirect('employees:job_title_list')
    else:
        form = JobTitleForm()

    menu_items = _get_menu_items(request, active_label='Job Titles')

    context = {
        'form': form,
        'action': 'create',
        'title': _('Add Job Title'),
        'menu_items': menu_items,
    }
    return render(request, 'employees/job_title_form.html', context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET', 'POST'])
def job_title_edit(request, pk):
    """
    Job title edit view. Restricted to ADMIN and HR.
    """
    job_title = get_object_or_404(JobTitle, pk=pk)

    if request.method == 'POST':
        form = JobTitleForm(request.POST, instance=job_title)
        if form.is_valid():
            job_title = form.save(commit=False)
            job_title.save(audit_actor=request.user, audit_request=request)
            form.save_m2m()

            messages.success(
                request,
                _('Job title "%(title)s" was successfully updated.') % {
                    'title': job_title.title,
                }
            )
            return redirect('employees:job_title_list')
    else:
        form = JobTitleForm(instance=job_title)

    menu_items = _get_menu_items(request, active_label='Job Titles')

    context = {
        'form': form,
        'job_title': job_title,
        'action': 'edit',
        'title': _('Edit Job Title'),
        'menu_items': menu_items,
    }
    return render(request, 'employees/job_title_form.html', context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_http_methods(['GET', 'POST'])
def job_title_delete(request, pk):
    """
    Job title deletion confirmation and execution view. Restricted to ADMIN and HR.
    Never deletes on GET.
    Prevents deletion if assigned employees exist.
    """
    job_title = get_object_or_404(
        JobTitle.objects.annotate(employee_count=Count('employees')),
        pk=pk
    )

    if request.method == 'POST':
        if job_title.employee_count > 0 or job_title.employees.exists():
            messages.error(
                request,
                _(
                    'Cannot delete job title "%(title)s" because %(count)d '
                    'employee(s) have this position. Please reassign them first.'
                ) % {
                    'title': job_title.title,
                    'count': job_title.employee_count,
                }
            )
            return redirect('employees:job_title_list')

        try:
            title_name = job_title.title
            job_title.delete(audit_actor=request.user, audit_request=request)
            messages.success(
                request,
                _('Job title "%(title)s" was successfully deleted.') % {
                    'title': title_name,
                }
            )
            return redirect('employees:job_title_list')
        except ProtectedError:
            messages.error(
                request,
                _('Job title "%(title)s" cannot be deleted because it is referenced by other records.') % {
                    'title': job_title.title,
                }
            )
            return redirect('employees:job_title_list')

    menu_items = _get_menu_items(request, active_label='Job Titles')

    context = {
        'job_title': job_title,
        'has_assigned_employees': (job_title.employee_count > 0 or job_title.employees.exists()),
        'menu_items': menu_items,
    }
    return render(request, 'employees/job_title_confirm_delete.html', context)
