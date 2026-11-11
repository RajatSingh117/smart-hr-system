
import calendar
from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Count
from django.utils import timezone

from apps.employees.models import Department

from .models import Attendance


def _status_totals(records):
    totals = {status: 0 for status in Attendance.Status.values}
    for row in records.values("status").annotate(total=Count("id")):
        totals[row["status"]] = row["total"]
    totals["total_records"] = sum(totals.values())
    return totals


def get_monthly_attendance_totals(year, month, department=None):
    """Organization-wide attendance counts per status for one month.

    Counts stored records only. Days without a record are not counted.
    `department` can be a Department instance or its id.
    """
    if not 1 <= month <= 12:
        raise ValidationError("Month must be between 1 and 12.")

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    records = Attendance.objects.filter(date__range=(first_day, last_day))
    if department is not None:
        records = records.filter(employee__department=department)
    return _status_totals(records)


def get_daily_attendance_totals(day, department=None):
    """Attendance counts per status for one day, from stored records."""
    records = Attendance.objects.filter(date=day)
    if department is not None:
        records = records.filter(employee__department=department)
    return _status_totals(records)


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
    row = {status: 0 for status in Attendance.Status.values}
    row.update(
        {"department_id": department_id, "department": name, "total_records": 0}
    )
    return row


def get_attendance_totals_by_department(year, month):
    """One row per department with attendance counts for a month.

    Departments with no records are included with zeros. Employees without
    a department are grouped under "No department", shown only if they
    have records.
    """
    if not 1 <= month <= 12:
        raise ValidationError("Month must be between 1 and 12.")

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    rows = {
        department.pk: _empty_department_row(department.pk, department.name)
        for department in Department.objects.order_by("name")
    }
    rows[None] = _empty_department_row(None, "No department")

    counts = (
        Attendance.objects.filter(date__range=(first_day, last_day))
        .values("employee__department_id", "status")
        .annotate(total=Count("id"))
    )
    for item in counts:
        row = rows[item["employee__department_id"]]
        row[item["status"]] = item["total"]
        row["total_records"] += item["total"]

    result = [row for key, row in rows.items() if key is not None]
    if rows[None]["total_records"]:
        result.append(rows[None])
    return result


def get_monthly_attendance_trend(months=6, today=None):
    """Monthly totals for the last `months` months, oldest first."""
    if not 1 <= months <= 24:
        raise ValidationError("Months must be between 1 and 24.")

    today = today or timezone.localdate()
    trend = []
    for year, month in _last_months(months, today):
        row = get_monthly_attendance_totals(year, month)
        row.update({"year": year, "month": month, "label": f"{year}-{month:02d}"})
        trend.append(row)
    return trend

def get_monthly_attendance_by_employee(year, month, employee=None):
    """One row per employee with attendance counts for one month.

    Used by the monthly summary page. Counts stored records only, and only
    employees with at least one record in the month get a row. Pass
    `employee` to limit the result to that single employee (employees see
    only their own numbers).
    """
    if not 1 <= month <= 12:
        raise ValidationError("Month must be between 1 and 12.")

    first_day = date(year, month, 1)
    last_day = date(year, month, calendar.monthrange(year, month)[1])

    records = Attendance.objects.filter(date__range=(first_day, last_day))
    if employee is not None:
        records = records.filter(employee=employee)

    rows = {}
    counts = (
        records.values("employee_id", "employee__full_name", "employee__employee_id", "status")
        .annotate(total=Count("id"))
        .order_by("employee__full_name", "employee_id")
    )
    for item in counts:
        row = rows.get(item["employee_id"])
        if row is None:
            row = {status: 0 for status in Attendance.Status.values}
            row.update(
                {
                    "employee_pk": item["employee_id"],
                    "employee": item["employee__full_name"],
                    "employee_code": item["employee__employee_id"],
                    "total_records": 0,
                }
            )
            rows[item["employee_id"]] = row
        row[item["status"]] = item["total"]
        row["total_records"] += item["total"]
    return list(rows.values())