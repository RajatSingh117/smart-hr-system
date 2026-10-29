from django.urls import path
from django.views.generic import RedirectView

from . import data_views, stub_views,  views
from .stub_views import SimplePreview

app_name = "reports"

urlpatterns = [
    path("", views.DashboardRedirectView.as_view(), name="dashboard"),
    path("admin/", views.AdminDashboardView.as_view(), name="admin_dashboard"),
    path("hr/", views.HRDashboardView.as_view(), name="hr_dashboard"),
    path("employee/", views.EmployeeDashboardView.as_view(), name="employee_dashboard"),

    # Employees
    path("preview/employees/", data_views.RealEmployeeList.as_view(), name="preview_employee_list"),
    path("preview/employees/new/", SimplePreview.as_view(template_name="employees/employee_form.html"), name="preview_employee_form"),
    path("preview/employees/<int:pk>/", data_views.RealEmployeeDetail.as_view(), name="preview_employee_detail"),
    path("preview/employees/<int:pk>/edit/", data_views.RealEmployeeEdit.as_view(), name="preview_employee_edit"),

    # Departments
    path("preview/departments/", data_views.RealDepartmentList.as_view(), name="preview_department_list"),
    path("preview/departments/new/", SimplePreview.as_view(template_name="employees/department_form.html"), name="preview_department_create"),

    # Attendance
    path("preview/attendance/", data_views.RealAttendanceList.as_view(), name="preview_attendance_list"),
    path("preview/attendance/check/", RedirectView.as_view(pattern_name="reports:preview_attendance_list"), name="preview_attendance_check"),
    path("preview/attendance/summary/", data_views.RealMonthlySummary.as_view(), name="preview_attendance_summary"),
    path("preview/attendance/correct/", SimplePreview.as_view(template_name="attendance/correction_form.html"), name="preview_attendance_correct"),

    # Leave
    path("preview/leave/", data_views.RealLeaveList.as_view(), name="preview_leave_list"),
    path("preview/leave/apply/", SimplePreview.as_view(template_name="leave/leave_apply.html"), name="preview_leave_apply"),
    path("preview/leave/<int:pk>/review/", data_views.RealLeaveReview.as_view(), name="preview_leave_review"),

    # Payroll
    path("preview/payroll/", stub_views.PayrollListPreview.as_view(), name="preview_payroll_list"),
    path("preview/payslips/", stub_views.MyPayslipsPreview.as_view(), name="preview_my_payslips"),
    path("preview/payslips/<int:pk>/", stub_views.PayslipDetailPreview.as_view(), name="preview_payslip_detail"),

    # Notifications
    path("preview/notifications/", stub_views.NotificationListPreview.as_view(), name="preview_notification_list"),
]

