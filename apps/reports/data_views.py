"""Real-data versions of the Week 2 pages (M3 employees, M4 attendance and leave).

Access rules:
- Employee list/edit, department list, leave review, monthly summary: Admin/HR only.
- Employee detail: Admin/HR, or an employee viewing their own page.
- Attendance and leave lists: Admin/HR see everyone, employees see only their own rows.
"""
from datetime import date

from django.contrib.auth.mixins import UserPassesTestMixin

from apps.attendance.models import Attendance

from . import real_data
from .access import RoleRequiredMixin, employee_for, is_hr_or_admin
from .stub_views import (
    AttendanceListPreview,
    DepartmentListPreview,
    EmployeeDetailPreview,
    EmployeeEditPreview,
    EmployeeListPreview,
    LeaveListPreview,
    LeaveReviewPreview,
    MonthlySummaryPreview,
    PayrollListPreview,
    SimplePreview,
)


class OwnRecordsMixin:
    """Admin/HR see all rows. Everyone else sees only rows of their own employee."""

    def scoped(self, rows):
        user = self.request.user
        if is_hr_or_admin(user):
            return rows
        employee = employee_for(user)
        if employee is None:
            return []
        return [r for r in rows if r.get("employee_pk") == employee.pk]


class RealEmployeeList(RoleRequiredMixin, EmployeeListPreview):
    @property
    def items(self):
        return real_data.get_employees()


class RealEmployeeDetail(UserPassesTestMixin, EmployeeDetailPreview):
    """Admin/HR, or the employee who owns this page."""

    def test_func(self):
        user = self.request.user
        if is_hr_or_admin(user):
            return True
        employee = employee_for(user)
        return bool(employee and employee.pk == self.kwargs["pk"])

    @property
    def items(self):
        return real_data.get_employees()


class RealEmployeeEdit(RoleRequiredMixin, EmployeeEditPreview):
    @property
    def items(self):
        return real_data.get_employees()


class RealDepartmentList(RoleRequiredMixin, DepartmentListPreview):
    @property
    def items(self):
        return real_data.get_departments()


class RealAttendanceList(OwnRecordsMixin, AttendanceListPreview):
    @property
    def items(self):
        return self.scoped(real_data.get_attendance())


class RealLeaveList(OwnRecordsMixin, LeaveListPreview):
    @property
    def items(self):
        return self.scoped(real_data.get_leaves())


class RealLeaveReview(RoleRequiredMixin, LeaveReviewPreview):
    @property
    def items(self):
        return real_data.get_leaves()


class RealMonthlySummary(RoleRequiredMixin, MonthlySummaryPreview):
    KEYS = ("present", "absent", "late", "half_day", "on_leave")

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        value = self.request.GET.get("month") or today.strftime("%Y-%m")
        try:
            year, mon = (int(x) for x in value.split("-"))
            date(year, mon, 1)
        except ValueError:
            year, mon = today.year, today.month
        value = f"{year:04d}-{mon:02d}"

        records = Attendance.objects.filter(
            date__year=year, date__month=mon
        ).select_related("employee")
        table = {}
        for rec in records:
            row = table.setdefault(
                rec.employee_id,
                {"employee": rec.employee.full_name, **{k: 0 for k in self.KEYS}},
            )
            status = str(rec.status).lower().replace("-", "_").replace(" ", "_")
            if status == "leave":
                status = "on_leave"
            if status in self.KEYS:
                row[status] += 1
        rows = sorted(table.values(), key=lambda r: r["employee"])
        totals = {k: sum(r[k] for r in rows) for k in self.KEYS}
        ctx.update({"month": value, "rows": rows, "totals": totals})
        return ctx

class HRSimplePreview(RoleRequiredMixin, SimplePreview):
    """Form and static pages that only Admin/HR may open."""


class HRPayrollList(RoleRequiredMixin, PayrollListPreview):
    pass

class ExportsPage(RoleRequiredMixin, SimplePreview):
    template_name = "reports/exports.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["datasets"] = [
            ("Employees", "employees"),
            ("Attendance", "attendance"),
            ("Leave requests", "leaves"),
        ]
        return ctx