"""
Reusable dashboard aggregation queries and analytics utilities for M3 (Employees & Departments).

Designed for consumption by M6 dashboards, KPI cards, and Chart.js visualizations.
Handles edge cases including:
- Zero employees in database
- Zero departments in database
- Empty departments (departments with 0 employees)
- Employees with unassigned department (department=None)
- Employees with unassigned job title (job_title=None)
- Terminated and on-leave employees
- Inactive departments and inactive job titles
"""
from decimal import Decimal
from typing import Any, Dict, List, Optional

from django.db.models import Case, Count, IntegerField, Q, Sum, When
from django.db.models.functions import Coalesce

from .models import Department, Employee, JobTitle


def get_total_headcount() -> int:
    """
    Return total count of all employee records in the system.
    Returns 0 if no employees exist.
    """
    return Employee.objects.count()


def get_active_headcount() -> int:
    """
    Return total count of currently ACTIVE employees.
    Returns 0 if no active employees exist.
    """
    return Employee.objects.filter(
        employment_status=Employee.EmploymentStatus.ACTIVE
    ).count()


def get_headcount_summary() -> Dict[str, int]:
    """
    Return headcount summary dictionary broken down by status in a single aggregated query.
    Guarantees 'total', 'active', 'on_leave', and 'terminated' are always present.
    """
    agg = Employee.objects.aggregate(
        total=Count('id'),
        active=Count(
            Case(
                When(employment_status=Employee.EmploymentStatus.ACTIVE, then=1),
                output_field=IntegerField(),
            )
        ),
        on_leave=Count(
            Case(
                When(employment_status=Employee.EmploymentStatus.ON_LEAVE, then=1),
                output_field=IntegerField(),
            )
        ),
        terminated=Count(
            Case(
                When(employment_status=Employee.EmploymentStatus.TERMINATED, then=1),
                output_field=IntegerField(),
            )
        ),
    )
    return {
        'total': agg['total'] or 0,
        'active': agg['active'] or 0,
        'on_leave': agg['on_leave'] or 0,
        'terminated': agg['terminated'] or 0,
    }


def get_department_employee_counts(
    active_only: bool = False,
    include_empty: bool = True,
    active_departments_only: bool = False,
) -> List[Dict[str, Any]]:
    """
    Return employee counts and salary aggregations for every department.

    Parameters:
    - active_only: If True, only counts employees with status=ACTIVE.
    - include_empty: If True, includes departments with 0 employees.
    - active_departments_only: If True, only queries departments where is_active=True.

    Handles edge cases:
    - Departments with zero assigned employees (reported with count=0).
    - Employees without an assigned department (reported under 'Unassigned' if count > 0).
    """
    dept_qs = Department.objects.all()
    if active_departments_only:
        dept_qs = dept_qs.filter(is_active=True)

    dept_qs = dept_qs.select_related('department_head').order_by('name')

    # Build annotations for total and active employees and salary sum
    dept_qs = dept_qs.annotate(
        total_emp_count=Count('employees'),
        active_emp_count=Count(
            Case(
                When(employees__employment_status=Employee.EmploymentStatus.ACTIVE, then=1),
                output_field=IntegerField(),
            )
        ),
    )

    results: List[Dict[str, Any]] = []
    for dept in dept_qs:
        count = dept.active_emp_count if active_only else dept.total_emp_count
        if not include_empty and count == 0:
            continue

        head_name = dept.department_head.full_name if dept.department_head else None
        results.append({
            'id': dept.id,
            'department_id': dept.id,
            'name': dept.name,
            'department_name': dept.name,
            'count': count,
            'total_count': dept.total_emp_count,
            'active_count': dept.active_emp_count,
            'total_salary': dept.total_base_salary,
            'is_active': dept.is_active,
            'department_head': head_name,
        })

    # Check for unassigned employees (department=None)
    unassigned_filter = Q(department__isnull=True)
    if active_only:
        unassigned_filter &= Q(employment_status=Employee.EmploymentStatus.ACTIVE)

    unassigned_emp_count = Employee.objects.filter(unassigned_filter).count()
    if unassigned_emp_count > 0:
        unassigned_active_count = Employee.objects.filter(
            department__isnull=True,
            employment_status=Employee.EmploymentStatus.ACTIVE,
        ).count()
        unassigned_salary = Employee.objects.filter(
            department__isnull=True,
            employment_status=Employee.EmploymentStatus.ACTIVE,
        ).aggregate(total=Sum('base_salary'))['total'] or Decimal('0.00')

        count = unassigned_active_count if active_only else unassigned_emp_count
        results.append({
            'id': None,
            'department_id': None,
            'name': 'Unassigned',
            'department_name': 'Unassigned',
            'count': count,
            'total_count': unassigned_emp_count,
            'active_count': unassigned_active_count,
            'total_salary': unassigned_salary,
            'is_active': True,
            'department_head': None,
        })

    return results


def get_employees_grouped_by_department(
    active_only: bool = False,
    active_departments_only: bool = False,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Return all employees grouped by their department name.
    Empty departments are included as empty lists [].
    Employees without a department are grouped under the 'Unassigned' key.
    """
    dept_qs = Department.objects.all()
    if active_departments_only:
        dept_qs = dept_qs.filter(is_active=True)
    dept_qs = dept_qs.order_by('name')

    grouped: Dict[str, List[Dict[str, Any]]] = {dept.name: [] for dept in dept_qs}

    emp_qs = Employee.objects.select_related('department', 'job_title').order_by('full_name')
    if active_only:
        emp_qs = emp_qs.filter(employment_status=Employee.EmploymentStatus.ACTIVE)

    unassigned: List[Dict[str, Any]] = []
    for emp in emp_qs:
        emp_data = {
            'id': emp.pk,
            'employee_id': emp.employee_id,
            'full_name': emp.full_name,
            'email': emp.email,
            'job_title': emp.job_title.title if emp.job_title else None,
            'status': emp.employment_status,
            'joining_date': emp.joining_date.isoformat() if emp.joining_date else None,
            'base_salary': float(emp.base_salary) if emp.base_salary is not None else 0.0,
        }
        if emp.department:
            if emp.department.name in grouped:
                grouped[emp.department.name].append(emp_data)
            else:
                grouped[emp.department.name] = [emp_data]
        else:
            unassigned.append(emp_data)

    if unassigned:
        grouped['Unassigned'] = unassigned

    return grouped


def get_status_distribution() -> Dict[str, int]:
    """
    Return distribution dictionary mapping employment status codes to counts.
    Guarantees ACTIVE, ON_LEAVE, and TERMINATED are present even if count is 0.
    """
    distribution = {
        Employee.EmploymentStatus.ACTIVE.value: 0,
        Employee.EmploymentStatus.ON_LEAVE.value: 0,
        Employee.EmploymentStatus.TERMINATED.value: 0,
    }
    counts = Employee.objects.values('employment_status').annotate(total=Count('id'))
    for row in counts:
        status_key = row['employment_status']
        if status_key in distribution:
            distribution[status_key] = row['total']
    return distribution


def get_job_title_distribution(
    active_only: bool = False,
    include_empty: bool = True,
) -> List[Dict[str, Any]]:
    """
    Return employee counts grouped by JobTitle.
    Handles job titles with 0 employees and unassigned employees (job_title=None).
    """
    title_qs = JobTitle.objects.all().order_by('title')
    title_qs = title_qs.annotate(
        total_count=Count('employees'),
        active_count=Count(
            Case(
                When(employees__employment_status=Employee.EmploymentStatus.ACTIVE, then=1),
                output_field=IntegerField(),
            )
        ),
    )

    results: List[Dict[str, Any]] = []
    for title in title_qs:
        count = title.active_count if active_only else title.total_count
        if not include_empty and count == 0:
            continue
        results.append({
            'id': title.id,
            'title': title.title,
            'count': count,
            'total_count': title.total_count,
            'active_count': title.active_count,
            'is_active': title.is_active,
        })

    # Unassigned job title
    unassigned_filter = Q(job_title__isnull=True)
    if active_only:
        unassigned_filter &= Q(employment_status=Employee.EmploymentStatus.ACTIVE)

    unassigned_count = Employee.objects.filter(unassigned_filter).count()
    if unassigned_count > 0:
        results.append({
            'id': None,
            'title': 'Unassigned',
            'count': unassigned_count,
            'total_count': Employee.objects.filter(job_title__isnull=True).count(),
            'active_count': Employee.objects.filter(
                job_title__isnull=True,
                employment_status=Employee.EmploymentStatus.ACTIVE,
            ).count(),
            'is_active': True,
        })

    return results


def get_dashboard_analytics() -> Dict[str, Any]:
    """
    Consolidated analytics package ready for direct consumption by M6 dashboards and Chart.js.
    Provides counts, breakdowns, percentages, and chart-ready label/data lists.
    """
    headcount = get_headcount_summary()
    dept_counts = get_department_employee_counts(active_only=False, include_empty=True)
    status_dist = get_status_distribution()
    job_dist = get_job_title_distribution(active_only=False, include_empty=False)

    total_employees = headcount['total']

    # Chart.js friendly structures
    dept_chart_labels = [d['name'] for d in dept_counts]
    dept_chart_data = [d['count'] for d in dept_counts]

    status_labels = ['Active', 'On Leave', 'Terminated']
    status_keys = [
        Employee.EmploymentStatus.ACTIVE.value,
        Employee.EmploymentStatus.ON_LEAVE.value,
        Employee.EmploymentStatus.TERMINATED.value,
    ]
    status_chart_data = [status_dist.get(k, 0) for k in status_keys]

    return {
        'headcount': headcount,
        'department_distribution': dept_counts,
        'status_distribution': status_dist,
        'job_title_distribution': job_dist,
        'department_count': Department.objects.filter(is_active=True).count(),
        'charts': {
            'departments': {
                'labels': dept_chart_labels,
                'data': dept_chart_data,
            },
            'status': {
                'labels': status_labels,
                'data': status_chart_data,
            },
        },
    }

