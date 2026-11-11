"""
Service layer and query exports for apps.employees.
Provides backward and forward compatibility with team members importing from services or queries.
"""
from .queries import (
    get_active_headcount,
    get_dashboard_analytics,
    get_department_employee_counts,
    get_employees_grouped_by_department,
    get_headcount_summary,
    get_job_title_distribution,
    get_status_distribution,
    get_total_headcount,
)

__all__ = [
    'get_total_headcount',
    'get_active_headcount',
    'get_headcount_summary',
    'get_department_employee_counts',
    'get_employees_grouped_by_department',
    'get_status_distribution',
    'get_job_title_distribution',
    'get_dashboard_analytics',
]

