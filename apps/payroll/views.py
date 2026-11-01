from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST, require_GET

from apps.accounts.models import User

from .models import PayrollRecord, Payslip
from .pdf_services import generate_payslip_pdf


def _is_hr_or_admin(user):
    """Check whether the user can manage payroll."""
    return user.role in (
        User.Role.ADMIN,
        User.Role.HR,
    )


@login_required
@require_POST
def generate_payslip(request, payroll_record_id):
    """
    Allow HR and Admin users to generate a payslip PDF.
    The generated PDF is returned as a download.
    """

    if not _is_hr_or_admin(request.user):
        raise PermissionDenied(
            "Only HR and Admin users can generate payslips."
        )

    payroll_record = get_object_or_404(
        PayrollRecord.objects.select_related(
            "employee",
            "payroll_period",
        ),
        pk=payroll_record_id,
    )

    payslip = generate_payslip_pdf(payroll_record)

    if (
        payslip.status != Payslip.Status.GENERATED
        or not payslip.pdf_file
    ):
        raise Http404("Payslip PDF could not be generated.")

    return FileResponse(
        payslip.pdf_file.open("rb"),
        as_attachment=True,
        filename=f"{payslip.payslip_number}.pdf",
        content_type="application/pdf",
    )


@login_required
@require_GET
def download_payslip(request, payslip_id):
    """
    Allow employees to download only their own payslips.
    HR and Admin users can download any generated payslip.
    """

    payslip = get_object_or_404(
        Payslip.objects.select_related(
            "payroll_record__employee",
            "payroll_record__payroll_period",
        ),
        pk=payslip_id,
    )

    employee = payslip.payroll_record.employee

    if not _is_hr_or_admin(request.user):
        if request.user.role != User.Role.EMPLOYEE:
            raise PermissionDenied("Access denied.")

        if employee.user_id != request.user.pk:
            raise PermissionDenied(
                "You can only download your own payslips."
            )

    if (
        payslip.status != Payslip.Status.GENERATED
        or not payslip.pdf_file
    ):
        raise Http404("Payslip PDF is not available.")

    return FileResponse(
        payslip.pdf_file.open("rb"),
        as_attachment=True,
        filename=f"{payslip.payslip_number}.pdf",
        content_type="application/pdf",
    )