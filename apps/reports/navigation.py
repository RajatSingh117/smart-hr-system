
from django.urls import NoReverseMatch, reverse

ADMIN = "admin"
HR = "hr"
EMPLOYEE = "employee"

MENU = [
    {"label": "Dashboard", "icon": "📊", "url_name": "reports:dashboard", "roles": {ADMIN, HR, EMPLOYEE}},
    {"label": "Employees", "icon": "👥", "url_name": "employees:list", "roles": {ADMIN, HR}},
    {"label": "Departments", "icon": "🏢", "url_name": "employees:department_list", "roles": {ADMIN, HR}},
    {"label": "Attendance", "icon": "✅", "url_name": "attendance:list", "roles": {ADMIN, HR, EMPLOYEE}},
    {"label": "Leave", "icon": "🌴", "url_name": "leave_management:list", "roles": {ADMIN, HR, EMPLOYEE}},
    {"label": "Payroll", "icon": "💰", "url_name": "payroll:list", "roles": {ADMIN, HR}},
    {"label": "My Payslips", "icon": "📄", "url_name": "payroll:my_payslips", "roles": {EMPLOYEE}},
    {"label": "Reports", "icon": "📈", "url_name": "reports:summary", "roles": {ADMIN, HR}},
    {"label": "Audit Log", "icon": "🛡️", "url_name": "accounts:audit_log", "roles": {ADMIN}},
]


def _safe_reverse(url_name):
    try:
        return reverse(url_name)
    except NoReverseMatch:
        return "#"


def menu_for_role(role, current_path=""):
    """Return the menu items a given role may see, with resolved URLs."""
    items = []
    for entry in MENU:
        if role in entry["roles"]:
            url = _safe_reverse(entry["url_name"])
            items.append(
                {
                    "label": entry["label"],
                    "icon": entry["icon"],
                    "url": url,
                    "active": url != "#" and current_path.startswith(url) and url != "/",
                }
            )
    return items