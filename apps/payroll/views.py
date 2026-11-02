from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST, require_GET

from rest_framework import generics, permissions
from rest_framework.authentication import (
    TokenAuthentication,
    SessionAuthentication,
)
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.views import APIView

from apps.accounts.models import User

from .models import PayrollRecord, Payslip
from .serializers import PayrollRecordSerializer, PayslipSerializer
from .pdf_services import generate_payslip_pdf


def _is_hr_or_admin(user):
    """Check whether the user can manage payroll."""
    return user.role in (
        User.Role.ADMIN,
        User.Role.HR,
    )


# --------------------------------------------------
# Existing Django views
# --------------------------------------------------

@login_required
@require_POST
def generate_payslip(request, payroll_record_id):
    """Allow HR and Admin users to generate a payslip PDF."""

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
    """Allow employees to download their own payslips."""

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


# --------------------------------------------------
# Payroll API permissions
# --------------------------------------------------

class PayrollAPIPermission(permissions.BasePermission):
    """
    HR and Admin can access all payroll data.
    Employees can access their own individual objects.
    """

    message = "You do not have permission to access this payroll data."

    def has_permission(self, request, view):
        return request.user.is_authenticated

    def has_object_permission(self, request, view, obj):

        if _is_hr_or_admin(request.user):
            return True

        if request.user.role != User.Role.EMPLOYEE:
            return False

        if isinstance(obj, PayrollRecord):
            return obj.employee.user_id == request.user.pk

        if isinstance(obj, Payslip):
            return (
                obj.payroll_record.employee.user_id
                == request.user.pk
            )

        return False


# --------------------------------------------------
# Payroll Record API
# --------------------------------------------------

class PayrollRecordListAPIView(generics.ListAPIView):

    serializer_class = PayrollRecordSerializer
    permission_classes = [PayrollAPIPermission]

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
    ]

    def get_queryset(self):

        user = self.request.user

        queryset = PayrollRecord.objects.select_related(
            "employee",
            "payroll_period",
        )

        if _is_hr_or_admin(user):
            return queryset

        raise DRFPermissionDenied(
            "Employees cannot access the payroll records list."
        )


class PayrollRecordDetailAPIView(generics.RetrieveAPIView):

    serializer_class = PayrollRecordSerializer
    permission_classes = [PayrollAPIPermission]

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
    ]

    def get_queryset(self):

        return PayrollRecord.objects.select_related(
            "employee",
            "payroll_period",
        )


# --------------------------------------------------
# Payslip API
# --------------------------------------------------

class PayslipListAPIView(generics.ListAPIView):

    serializer_class = PayslipSerializer
    permission_classes = [PayrollAPIPermission]

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
    ]

    def get_queryset(self):

        user = self.request.user

        queryset = Payslip.objects.select_related(
            "payroll_record__employee",
            "payroll_record__payroll_period",
        )

        if _is_hr_or_admin(user):
            return queryset

        raise DRFPermissionDenied(
            "Employees cannot access the payslips list."
        )


class PayslipDetailAPIView(generics.RetrieveAPIView):

    serializer_class = PayslipSerializer
    permission_classes = [PayrollAPIPermission]

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
    ]

    def get_queryset(self):

        return Payslip.objects.select_related(
            "payroll_record__employee",
            "payroll_record__payroll_period",
        )


# --------------------------------------------------
# Payslip PDF Download API
# --------------------------------------------------

class PayslipDownloadAPIView(APIView):

    permission_classes = [PayrollAPIPermission]

    authentication_classes = [
        TokenAuthentication,
        SessionAuthentication,
    ]

    def get(self, request, pk):

        payslip = get_object_or_404(
            Payslip.objects.select_related(
                "payroll_record__employee",
                "payroll_record__payroll_period",
            ),
            pk=pk,
        )

        self.check_object_permissions(request, payslip)

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