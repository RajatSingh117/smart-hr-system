from django.urls import path

from . import views

urlpatterns = [
    path(
        "records/",
        views.PayrollRecordListAPIView.as_view(),
        name="payroll-record-list",
    ),
    path(
        "records/<int:pk>/",
        views.PayrollRecordDetailAPIView.as_view(),
        name="payroll-record-detail",
    ),
    path(
        "payslips/",
        views.PayslipListAPIView.as_view(),
        name="payslip-list",
    ),
    path(
        "payslips/<int:pk>/",
        views.PayslipDetailAPIView.as_view(),
        name="payslip-detail",
    ),
    path(
        "payslips/<int:pk>/download/",
        views.PayslipDownloadAPIView.as_view(),
        name="payslip-download",
    ),
]