from datetime import date

from apps.attendance.models import Attendance

from . import real_data
from .stub_views import (
    AttendanceListPreview,
    DepartmentListPreview,
    EmployeeDetailPreview,
    EmployeeEditPreview,
    EmployeeListPreview,
    LeaveListPreview,
    LeaveReviewPreview,
    MonthlySummaryPreview,
)


class RealEmployeeList(EmployeeListPreview):
    @property
    def items(self):
        return real_data.get_employees()


class RealEmployeeDetail(EmployeeDetailPreview):
    @property
    def items(self):
        return real_data.get_employees()


class RealEmployeeEdit(EmployeeEditPreview):
    @property
    def items(self):
        return real_data.get_employees()


class RealDepartmentList(DepartmentListPreview):
    @property
    def items(self):
        return real_data.get_departments()


class RealAttendanceList(AttendanceListPreview):
    @property
    def items(self):
        return real_data.get_attendance()


class RealLeaveList(LeaveListPreview):
    @property
    def items(self):
        return real_data.get_leaves()


class RealLeaveReview(LeaveReviewPreview):
    @property
    def items(self):
        return real_data.get_leaves()


class RealMonthlySummary(MonthlySummaryPreview):
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