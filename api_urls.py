from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r"components", views.SalaryComponentViewSet, basename="salarycomponent")
router.register(r"periods", views.PayrollPeriodViewSet, basename="payrollperiod")
router.register(r"records", views.PayrollRecordViewSet, basename="payrollrecord")
router.register(r"payslips", views.PayslipViewSet, basename="payslip")
router.register(r"notifications", views.NotificationLogViewSet, basename="notificationlog")

urlpatterns = [
    path("", include(router.urls)),
    path(
        "payslips/<int:pk>/download/",
        views.PayslipDownloadAPIView.as_view(),
        name="payslip-download",
    ),
    path(
        "records/<int:payroll_record_id>/generate-payslip/",
        views.PayslipGenerateAPIView.as_view(),
        name="payslip-generate",
    ),
]