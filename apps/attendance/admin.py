from django.contrib import admin

from .models import Attendance


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "date",
        "status",
        "check_in",
        "check_out",
        "corrected_by",
    )
    list_filter = ("status", "date")
    search_fields = ("employee__full_name", "employee__employee_id")
    date_hierarchy = "date"
    readonly_fields = ("created_at", "updated_at")