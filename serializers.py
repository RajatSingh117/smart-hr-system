from rest_framework import serializers

from .models import PayrollRecord, Payslip, NotificationLog


class PayrollRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="employee.full_name",
        read_only=True
    )

    employee_id = serializers.CharField(
        source="employee.employee_id",
        read_only=True
    )

    payroll_period_name = serializers.CharField(
        source="payroll_period.name",
        read_only=True
    )

    class Meta:
        model = PayrollRecord
        fields = [
            "id",
            "employee",
            "employee_id",
            "employee_name",
            "payroll_period",
            "payroll_period_name",
            "basic_salary",
            "total_allowances",
            "total_deductions",
            "gross_salary",
            "net_salary",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class PayslipSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(
        source="payroll_record.employee.full_name",
        read_only=True
    )

    employee_id = serializers.CharField(
        source="payroll_record.employee.employee_id",
        read_only=True
    )

    payroll_period_name = serializers.CharField(
        source="payroll_record.payroll_period.name",
        read_only=True
    )

    class Meta:
        model = Payslip
        fields = [
            "id",
            "payroll_record",
            "employee_name",
            "employee_id",
            "payroll_period_name",
            "payslip_number",
            "pdf_file",
            "status",
            "generated_at",
        ]


class NotificationLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationLog
        fields = [
            "id",
            "recipient",
            "notification_type",
            "subject",
            "status",
            "error_message",
            "created_at",
            "sent_at",
        ]
        read_only_fields = fields