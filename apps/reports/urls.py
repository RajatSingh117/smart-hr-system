from django.urls import path
from django.views.generic import RedirectView

from . import stub_views, views
from .stub_views import SimplePreview

app_name = "reports"

urlpatterns = [
    path("", views.DashboardRedirectView.as_view(), name="dashboard"),
    path("admin/", views.AdminDashboardView.as_view(), name="admin_dashboard"),
    path("hr/", views.HRDashboardView.as_view(), name="hr_dashboard"),
    path("employee/", views.EmployeeDashboardView.as_view(), name="employee_dashboard"),

    # Employees
    path("preview/employees/", stub_views.EmployeeListPreview.as_view(), name="preview_employee_list"),
    path("preview/employees/new/", SimplePreview.as_view(template_name="employees/employee_form.html"), name="preview_employee_form"),
    path("preview/employees/<int:pk>/", stub_views.EmployeeDetailPreview.as_view(), name="preview_employee_detail"),
    path("preview/employees/<int:pk>/edit/", stub_views.EmployeeEditPreview.as_view(), name="preview_employee_edit"),

    # Departments
    path("preview/departments/", stub_views.DepartmentListPreview.as_view(), name="preview_department_list"),
    path("preview/departments/new/", SimplePreview.as_view(template_name="employees/department_form.html"), name="preview_department_create"),

    # Attendance
    path("preview/attendance/", stub_views.AttendanceListPreview.as_view(), name="preview_attendance_list"),
    path("preview/attendance/check/", RedirectView.as_view(pattern_name="reports:preview_attendance_list"), name="preview_attendance_check"),
    path("preview/attendance/summary/", stub_views.MonthlySummaryPreview.as_view(), name="preview_attendance_summary"),
    path("preview/attendance/correct/", SimplePreview.as_view(template_name="attendance/correction_form.html"), name="preview_attendance_correct"),

    # Leave
    path("preview/leave/", stub_views.LeaveListPreview.as_view(), name="preview_leave_list"),
    path("preview/leave/apply/", SimplePreview.as_view(template_name="leave/leave_apply.html"), name="preview_leave_apply"),
    path("preview/leave/<int:pk>/review/", stub_views.LeaveReviewPreview.as_view(), name="preview_leave_review"),
]