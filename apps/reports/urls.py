from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.DashboardRedirectView.as_view(), name="dashboard"),
    path("admin/", views.AdminDashboardView.as_view(), name="admin_dashboard"),
    path("hr/", views.HRDashboardView.as_view(), name="hr_dashboard"),
    path("employee/", views.EmployeeDashboardView.as_view(), name="employee_dashboard"),
]