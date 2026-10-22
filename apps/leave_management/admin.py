from django.contrib import admin
from .models import (
    LeaveBalance,
    LeaveRequest,
    LeaveStatusHistory,
    LeaveType,
    PublicHoliday,
)

from .models import LeaveBalance, LeaveRequest, LeaveStatusHistory, LeaveType


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)


@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ("employee", "leave_type", "year", "remaining_days")
    list_filter = ("year", "leave_type")
    search_fields = ("employee__full_name", "employee__employee_id")
    readonly_fields = ("updated_at",)


class LeaveStatusHistoryInline(admin.TabularInline):
    model = LeaveStatusHistory
    extra = 0
    can_delete = False
    readonly_fields = ("old_status", "new_status", "changed_by", "remarks", "changed_at")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "leave_type",
        "start_date",
        "end_date",
        "status",
        "approver",
        "decided_at",
    )
    list_filter = ("status", "leave_type")
    search_fields = ("employee__full_name", "employee__employee_id")
    readonly_fields = ("created_at", "updated_at")
    inlines = [LeaveStatusHistoryInline]
@admin.register(PublicHoliday)
class PublicHolidayAdmin(admin.ModelAdmin):
    list_display = ("name", "date")
    list_filter = ("date",)
    search_fields = ("name",)
    ordering = ("date",)
    
