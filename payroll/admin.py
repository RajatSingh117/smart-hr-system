from django.contrib import admin

from .models import (
    SalaryComponent,
    PayrollPeriod,
    PayrollRecord,
    Payslip,
    NotificationLog,
)


@admin.register(SalaryComponent)
class SalaryComponentAdmin(admin.ModelAdmin):
    list_display = ["name", "component_type", "amount", "is_active", "created_at"]
    list_filter = ["component_type", "is_active"]
    search_fields = ["name"]
    readonly_fields = ["created_at"]


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(admin.ModelAdmin):
    list_display = ["name", "start_date", "end_date", "is_processed", "created_at"]
    list_filter = ["is_processed"]
    search_fields = ["name"]
    readonly_fields = ["created_at"]


@admin.register(PayrollRecord)
class PayrollRecordAdmin(admin.ModelAdmin):
    list_display = [
        "employee",
        "payroll_period",
        "gross_salary",
        "net_salary",
        "created_at",
    ]
    list_filter = ["payroll_period"]
    search_fields = ["employee__full_name"]
    readonly_fields = ["gross_salary", "net_salary", "created_at", "updated_at"]


@admin.register(Payslip)
class PayslipAdmin(admin.ModelAdmin):
    list_display = ["payslip_number", "payroll_record", "status", "generated_at"]
    list_filter = ["status"]
    search_fields = ["payslip_number", "payroll_record__employee__full_name"]
    readonly_fields = ["payslip_number", "generated_at"]


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = [
        "notification_type",
        "recipient",
        "subject",
        "status",
        "created_at",
    ]
    list_filter = ["notification_type", "status"]
    search_fields = ["recipient", "subject"]
    readonly_fields = [
        "recipient",
        "notification_type",
        "subject",
        "status",
        "error_message",
        "created_at",
        "sent_at",
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False