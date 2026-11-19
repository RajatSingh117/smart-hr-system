
from django.urls import NoReverseMatch, reverse

ADMIN = "admin"
HR = "hr"
EMPLOYEE = "employee"

MENU = [
    {"label": "Dashboard", "icon": "bi bi-speedometer2", "url_name": "reports:dashboard", "roles": {ADMIN, HR, EMPLOYEE}},
    {"label": "Employees", "icon": "bi bi-people", "url_name": "employees:list", "roles": {ADMIN, HR}},
    {"label": "Departments", "icon": "bi bi-building", "url_name": "employees:department_list", "roles": {ADMIN, HR}},
    {"label": "Job Titles", "icon": "bi bi-briefcase", "url_name": "employees:job_title_list", "roles": {ADMIN, HR}},
    {"label": "Attendance", "icon": "bi bi-calendar-check", "url_name": "attendance:list", "roles": {ADMIN, HR, EMPLOYEE}},
    {"label": "Leave", "icon": "bi bi-calendar2-range", "url_name": "leave_management:list", "roles": {ADMIN, HR, EMPLOYEE}},
    {"label": "Payroll", "icon": "bi bi-cash-stack", "url_name": "payroll:list", "roles": {ADMIN, HR}},
    {"label": "My Payslips", "icon": "bi bi-receipt", "url_name": "payroll:my_payslips", "roles": {EMPLOYEE}},
    {"label": "Reports", "icon": "bi bi-file-earmark-bar-graph", "url_name": "reports:exports", "roles": {ADMIN, HR}},
    {"label": "Charts", "icon": "bi bi-pie-chart", "url_name": "reports:charts", "roles": {ADMIN, HR}},
    {"label": "My Profile", "icon": "bi bi-person-circle", "url_name": "accounts:profile", "roles": {ADMIN, HR, EMPLOYEE}},
    {"label": "Django Admin", "icon": "bi bi-sliders", "url_name": "admin:index", "roles": {ADMIN}},
    {"label": "Audit Log", "icon": "bi bi-shield-check", "url_name": "accounts:audit_log", "roles": {ADMIN}},
]


def _safe_reverse(url_name):
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return "#"


def menu_for_role(role, current_path="", valid_only=False):
    """Return the menu items a given role may see, with resolved URLs."""
    role_str = str(role or "").lower()
    items = []
    for entry in MENU:
        if role_str in {r.lower() for r in entry["roles"]}:
            url = _safe_reverse(entry["url_name"])
            if valid_only and (not url or url == "#"):
                continue

            # Determine active state
            is_active = False
            if url and url != "#":
                if entry["label"] == "Dashboard":
                    is_active = (
                        current_path == url
                        or "dashboard" in current_path
                        or current_path.startswith("/reports/admin")
                        or current_path.startswith("/reports/hr")
                        or current_path.startswith("/reports/employee")
                        or current_path == "/reports/"
                    )
                elif entry["label"] == "Employees":
                    is_active = (
                        current_path.startswith(url)
                        or (
                            current_path.startswith("/employees")
                            and not current_path.startswith("/employees/departments")
                            and not current_path.startswith("/employees/job-titles")
                        )
                    )
                elif entry["label"] == "Departments":
                    is_active = current_path.startswith(url) or current_path.startswith("/employees/departments")
                elif entry["label"] == "Job Titles":
                    is_active = current_path.startswith(url) or current_path.startswith("/employees/job-titles")
                elif entry["label"] == "Attendance":
                    is_active = current_path.startswith(url) or current_path.startswith("/attendance")
                elif entry["label"] == "Leave":
                    is_active = current_path.startswith(url) or current_path.startswith("/leave")
                elif entry["label"] == "Reports":
                    is_active = current_path.startswith(url) or current_path.startswith("/reports/exports")
                elif entry["label"] == "Charts":
                    is_active = current_path.startswith(url) or current_path.startswith("/reports/charts")
                elif entry["label"] == "My Profile":
                    is_active = current_path.startswith(url) or current_path.startswith("/accounts/profile")
                elif entry["label"] == "Django Admin":
                    is_active = current_path.startswith(url) or current_path.startswith("/admin")
                else:
                    is_active = current_path.startswith(url) and url != "/"

            items.append(
                {
                    "label": entry["label"],
                    "icon": entry["icon"],
                    "url": url,
                    "active": is_active,
                }
            )
    return items