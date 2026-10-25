"""Fake data for M6 preview pages. Replace with real M3/M4 data later."""
from django.core.paginator import Paginator

EMPLOYEES = [
    {"id": 1, "name": "Aarav Sharma", "email": "aarav@example.com", "department": "Engineering", "designation": "Developer", "join_date": "2024-01-15", "status": "Active"},
    {"id": 2, "name": "Priya Verma", "email": "priya@example.com", "department": "HR", "designation": "HR Executive", "join_date": "2023-08-01", "status": "Active"},
    {"id": 3, "name": "Rohan Gupta", "email": "rohan@example.com", "department": "Finance", "designation": "Accountant", "join_date": "2022-11-20", "status": "On Leave"},
    {"id": 4, "name": "Neha Singh", "email": "neha@example.com", "department": "Engineering", "designation": "Tester", "join_date": "2024-03-10", "status": "Active"},
    {"id": 5, "name": "Karan Mehta", "email": "karan@example.com", "department": "Sales", "designation": "Sales Lead", "join_date": "2021-06-05", "status": "Inactive"},
    {"id": 6, "name": "Sana Khan", "email": "sana@example.com", "department": "HR", "designation": "Recruiter", "join_date": "2025-02-18", "status": "Active"},
]

DEPARTMENTS = [
    {"id": 1, "name": "Engineering", "head": "Aarav Sharma", "employee_count": 12},
    {"id": 2, "name": "HR", "head": "Priya Verma", "employee_count": 4},
    {"id": 3, "name": "Finance", "head": "Rohan Gupta", "employee_count": 5},
    {"id": 4, "name": "Sales", "head": "Karan Mehta", "employee_count": 8},
]

ATTENDANCE = [
    {"id": 1, "employee": "Aarav Sharma", "date": "2026-10-20", "check_in": "09:05", "check_out": "18:02", "status": "Present"},
    {"id": 2, "employee": "Priya Verma", "date": "2026-10-20", "check_in": "09:40", "check_out": "18:10", "status": "Late"},
    {"id": 3, "employee": "Rohan Gupta", "date": "2026-10-20", "check_in": "-", "check_out": "-", "status": "Absent"},
    {"id": 4, "employee": "Neha Singh", "date": "2026-10-20", "check_in": "09:00", "check_out": "17:55", "status": "Present"},
]

MONTHLY_SUMMARY = {"month": "October 2026", "present": 18, "absent": 2, "late": 3, "leave": 1}

LEAVES = [
    {"id": 1, "employee": "Aarav Sharma", "leave_type": "Casual", "start_date": "2026-10-25", "end_date": "2026-10-26", "reason": "Family function", "status": "Pending"},
    {"id": 2, "employee": "Rohan Gupta", "leave_type": "Sick", "start_date": "2026-10-18", "end_date": "2026-10-20", "reason": "Fever", "status": "Approved"},
    {"id": 3, "employee": "Neha Singh", "leave_type": "Casual", "start_date": "2026-10-10", "end_date": "2026-10-10", "reason": "Personal", "status": "Rejected"},
]


def filter_items(items, q="", status="", fields=("name",)):
    """Simple search on given fields plus exact match on status."""
    q = (q or "").strip().lower()
    result = []
    for item in items:
        if status and item.get("status", "").lower() != status.lower():
            continue
        if q and not any(q in str(item.get(f, "")).lower() for f in fields):
            continue
        result.append(item)
    return result


def paginate(request, items, per_page=5):
    return Paginator(items, per_page).get_page(request.GET.get("page"))