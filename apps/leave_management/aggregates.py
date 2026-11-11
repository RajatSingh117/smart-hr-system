from django.db.models import (
    Avg,
    Count,
    DurationField,
    ExpressionWrapper,
    F,
)
from django.utils import timezone
from .models import LeaveBalance, LeaveRequest
import calendar 
from datetime import date
from django.core.exceptions import ValidationError
from apps.employees.models import Department




def _filter_requests(requests, department, start_date, end_date, date_field):
    if department is not None:
        requests = requests.filter(employee__department=department)
    if start_date is not None:
        requests = requests.filter(**{f"{date_field}__date__gte": start_date})
    if end_date is not None:
        requests = requests.filter(**{f"{date_field}__date__lte": end_date})
    return requests


def get_pending_leave_count(department=None, start_date=None, end_date=None):
    """Number of Pending requests, optionally by department and by the
    date the request was submitted (both ends inclusive)."""
    requests = LeaveRequest.objects.filter(status=LeaveRequest.Status.PENDING)
    return _filter_requests(
        requests, department, start_date, end_date, "created_at"
    ).count()


def get_average_approval_hours(department=None, start_date=None, end_date=None):
    """Mean hours from submission to decision.

    Only Approved and Rejected requests count, filtered by the date of the
    decision. Returns None when there is nothing to average.
    """
    decided = LeaveRequest.objects.filter(
        status__in=[
            LeaveRequest.Status.APPROVED,
            LeaveRequest.Status.REJECTED,
        ],
        decided_at__isnull=False,
    )
    decided = _filter_requests(
        decided, department, start_date, end_date, "decided_at"
    )
    duration = ExpressionWrapper(
        F("decided_at") - F("created_at"), output_field=DurationField()
    )
    average = decided.aggregate(average=Avg(duration))["average"]
    if average is None:
        return None
    return round(average.total_seconds() / 3600, 2)


def get_leave_requests_by_status(department=None, start_date=None, end_date=None):
    """Count of requests per status (zeros included) plus a total."""
    requests = _filter_requests(
        LeaveRequest.objects.all(),
        department,
        start_date,
        end_date,
        "created_at",
    )
    counts = {status: 0 for status in LeaveRequest.Status.values}
    for row in requests.values("status").annotate(total=Count("id")):
        counts[row["status"]] = row["total"]
    counts["total"] = sum(counts.values())
    return counts


def get_employees_on_leave_count(on_date=None, department=None):
    """Distinct employees with an Approved request covering the date."""
    on_date = on_date or timezone.localdate()
    requests = LeaveRequest.objects.filter(
        status=LeaveRequest.Status.APPROVED,
        start_date__lte=on_date,
        end_date__gte=on_date,
    )
    if department is not None:
        requests = requests.filter(employee__department=department)
    return requests.values("employee_id").distinct().count()


def get_employee_leave_dashboard(employee, year, recent_limit=5):
    """Data for one employee's dashboard cards. Own data only."""
    balances = (
        LeaveBalance.objects.filter(employee=employee, year=year)
        .select_related("leave_type")
        .order_by("leave_type__name")
    )
    recent = (
        LeaveRequest.objects.filter(employee=employee)
        .select_related("leave_type")
        .order_by("-created_at", "-id")[:recent_limit]
    )
    pending_count = LeaveRequest.objects.filter(
        employee=employee, status=LeaveRequest.Status.PENDING
    ).count()

    return {
        "balances": [
            {
                "leave_type": balance.leave_type.name,
                "remaining_days": balance.remaining_days,
            }
            for balance in balances
        ],
        "recent_requests": [
            {
                "id": request.pk,
                "leave_type": request.leave_type.name,
                "start_date": request.start_date,
                "end_date": request.end_date,
                "status": request.status,
            }
            for request in recent
        ],
        "pending_count": pending_count,
    }
def _last_months(count, today):
    """(year, month) pairs for the last `count` months, oldest first."""
    year, month = today.year, today.month
    months = []
    for _ in range(count):
        months.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    return list(reversed(months))


def _empty_department_row(department_id, name):
    row = {status: 0 for status in LeaveRequest.Status.values}
    row.update({"department_id": department_id, "department": name, "total": 0})
    return row

def get_leave_counts_by_department(start_date=None, end_date=None):
    """One row per department with leave request counts per status,
    by submission date. Departments without requests are included."""
    rows = {
        department.pk: _empty_department_row(department.pk, department.name)
        for department in Department.objects.order_by("name")
    }
    rows[None] = _empty_department_row(None, "No department")

    requests = _filter_requests(
        LeaveRequest.objects.all(), None, start_date, end_date, "created_at"
    )
    counts = requests.values("employee__department_id", "status").annotate(
        total=Count("id")
    )
    for item in counts:
        row = rows[item["employee__department_id"]]
        row[item["status"]] = item["total"]
        row["total"] += item["total"]

    result = [row for key, row in rows.items() if key is not None]
    if rows[None]["total"]:
        result.append(rows[None])
    return result


def get_monthly_leave_trend(months=6, today=None):
    """Leave request counts per status for the last `months` months, by
    submission month, oldest first."""
    if not 1 <= months <= 24:
        raise ValidationError("Months must be between 1 and 24.")

    today = today or timezone.localdate()
    trend = []
    for year, month in _last_months(months, today):
        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])
        row = get_leave_requests_by_status(
            start_date=first_day, end_date=last_day
        )
        row.update({"year": year, "month": month, "label": f"{year}-{month:02d}"})
        trend.append(row)
    return trend