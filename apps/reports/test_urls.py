from django.urls import include, path

urlpatterns = [
    path("accounts/", include("apps.accounts.urls", namespace="accounts")),
    path("dashboard/", include("apps.reports.urls")),
    path("attendance/", include("apps.attendance.urls", namespace="attendance")),
    path("leave/", include("apps.leave_management.urls", namespace="leave_management")),
]