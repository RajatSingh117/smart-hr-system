from apps.attendance.models import Attendance
from apps.employees.models import Department, Employee
from apps.leave_management.models import LeaveRequest


def _time(value):
    return value.strftime("%H:%M") if value else "-"


def _date(value):
    return value.isoformat() if value else "-"


def _text(value):
    return str(value).replace("_", " ").title() if value else "-"


def get_employees():
    rows = Employee.objects.select_related("department", "job_title").order_by("full_name")
    return [
        {
            "id": e.pk,
            "name": e.full_name,
            "email": e.email,
            "department": e.department.name if e.department else "-",
            "designation": str(e.job_title) if e.job_title else "-",
            "join_date": _date(e.joining_date),
            "status": _text(e.employment_status),
        }
        for e in rows
    ]


def get_departments():
    rows = Department.objects.select_related("department_head").order_by("name")
    return [
        {
            "id": d.pk,
            "name": d.name,
            "head": d.department_head.full_name if d.department_head else "-",
            "employee_count": d.employees.count(),
        }
        for d in rows
    ]


def get_attendance():
    rows = Attendance.objects.select_related("employee").order_by("-date")
    return [
        {
            "id": a.pk,
            "employee": a.employee.full_name,
            "date": _date(a.date),
            "check_in": _time(a.check_in),
            "check_out": _time(a.check_out),
            "status": _text(a.status),
        }
        for a in rows
    ]


def get_leaves():
    rows = LeaveRequest.objects.select_related("employee", "leave_type").order_by("-created_at")
    return [
        {
            "id": l.pk,
            "employee": l.employee.full_name,
            "leave_type": l.leave_type.name,
            "start_date": _date(l.start_date),
            "end_date": _date(l.end_date),
            "reason": l.reason,
            "status": _text(l.status),
        }
        for l in rows
    ]