from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST, require_GET

from rest_framework import generics, status, viewsets
from rest_framework.authentication import (
    TokenAuthentication,
    SessionAuthentication,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import CanAccessPayroll, IsHR

from .models import (
    SalaryComponent,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    NotificationLog,
)
from .serializers import (
    SalaryComponentSerializer,
    PayrollPeriodSerializer,
    PayrollRecordSerializer,
    PayslipSerializer,
    NotificationLogSerializer,
)
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
# Mixin for audit context
# --------------------------------------------------

class AuditMixin:
    """Mixin to pass audit context on save/delete."""

    def perform_create(self, serializer):
        instance = serializer.save()
        instance._audit_request = self.request
        instance._audit_actor = self.request.user
        instance.save()

    def perform_update(self, serializer):
        instance = serializer.save()
        instance._audit_request = self.request
        instance._audit_actor = self.request.user
        instance.save()

    def perform_destroy(self, instance):
        instance._audit_request = self.request
        instance._audit_actor = self.request.user
        instance.delete()


# --------------------------------------------------
# Base Payroll ViewSet with common queryset filtering
# --------------------------------------------------

class PayrollBaseViewSet(AuditMixin, viewsets.ModelViewSet):
    permission_classes = [CanAccessPayroll]
    authentication_classes = [TokenAuthentication, SessionAuthentication]

    def get_queryset(self):
        user = self.request.user
        queryset = self.queryset

        # HR and Admin can view all
        if _is_hr_or_admin(user):
            return queryset

        # Employees can view only their own
        if user.role == User.Role.EMPLOYEE:
            return self.filter_own(queryset, user)

        return queryset.none()


# --------------------------------------------------
# SalaryComponent API (HR/Admin only for write)
# --------------------------------------------------

class SalaryComponentViewSet(PayrollBaseViewSet):
    queryset = SalaryComponent.objects.all()
    serializer_class = SalaryComponentSerializer
    filterset_fields = ['component_type', 'is_active']
    search_fields = ['name']
    ordering = ['name']

    def filter_own(self, queryset, user):
        return queryset.none()  # Employees cannot see salary components

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsHR()]
        return super().get_permissions()


# --------------------------------------------------
# PayrollPeriod API (HR/Admin only for write)
# --------------------------------------------------

class PayrollPeriodViewSet(PayrollBaseViewSet):
    queryset = PayrollPeriod.objects.all()
    serializer_class = PayrollPeriodSerializer
    filterset_fields = ['is_processed']
    ordering = ['-start_date']

    def filter_own(self, queryset, user):
        return queryset.none()  # Employees cannot see periods

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsHR()]
        return super().get_permissions()


# --------------------------------------------------
# PayrollRecord API
# --------------------------------------------------

class PayrollRecordViewSet(PayrollBaseViewSet):
    queryset = PayrollRecord.objects.select_related(
        "employee", "payroll_period"
    )
    serializer_class = PayrollRecordSerializer
    filterset_fields = ['payroll_period', 'employee']
    search_fields = ['employee__full_name']
    ordering = ['-created_at']

    def filter_own(self, queryset, user):
        return queryset.filter(employee__user=user)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsHR()]
        return super().get_permissions()


# --------------------------------------------------
# Payslip API
# --------------------------------------------------

class PayslipViewSet(PayrollBaseViewSet):
    queryset = Payslip.objects.select_related(
        "payroll_record__employee", "payroll_record__payroll_period"
    )
    serializer_class = PayslipSerializer
    filterset_fields = ['status', 'payroll_record__payroll_period']
    ordering = ['-generated_at']

    def filter_own(self, queryset, user):
        return queryset.filter(payroll_record__employee__user=user)

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsHR()]
        return super().get_permissions()


# --------------------------------------------------
# NotificationLog API (read-only for employees)
# --------------------------------------------------

class NotificationLogViewSet(PayrollBaseViewSet):
    queryset = NotificationLog.objects.all()
    serializer_class = NotificationLogSerializer
    filterset_fields = ['notification_type', 'status']
    ordering = ['-created_at']
    http_method_names = ['get', 'head', 'options']  # read-only

    def filter_own(self, queryset, user):
        return queryset.filter(recipient=user.email)


# --------------------------------------------------
# Payslip PDF Download API
# --------------------------------------------------

class PayslipDownloadAPIView(APIView):
    permission_classes = [CanAccessPayroll]
    authentication_classes = [TokenAuthentication, SessionAuthentication]

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


# --------------------------------------------------
# Payslip Generation API (HR/Admin only)
# --------------------------------------------------

class PayslipGenerateAPIView(APIView):
    permission_classes = [IsHR]
    authentication_classes = [TokenAuthentication, SessionAuthentication]

    def post(self, request, payroll_record_id):
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
            return Response(
                {"error": "Payslip PDF could not be generated."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        serializer = PayslipSerializer(payslip)
        return Response(serializer.data, status=status.HTTP_201_CREATED)