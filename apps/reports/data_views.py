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
    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        today = date.today()
        month = Attendance.objects.filter(date__year=today.year, date__month=today.month)
        ctx["summary"] = {
            "month": today.strftime("%B %Y"),
            "present": month.filter(status__iexact="present").count(),
            "absent": month.filter(status__iexact="absent").count(),
            "late": month.filter(status__iexact="late").count(),
            "leave": month.filter(status__iexact="leave").count(),
        }
        return ctx