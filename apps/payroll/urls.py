from django.urls import path

from . import views

app_name = "payroll"

urlpatterns = [
    path(
        "generate/<int:payroll_record_id>/",
        views.generate_payslip,
        name="generate-payslip",
    ),
    path(
        "payslips/<int:payslip_id>/download/",
        views.download_payslip,
        name="download-payslip",
    ),
]