from django.contrib import admin
from .models import Department, JobTitle, Employee


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'department_head', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    ordering = ('name',)


@admin.register(JobTitle)
class JobTitleAdmin(admin.ModelAdmin):
    list_display = ('title', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('title', 'description')
    ordering = ('title',)


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'employee_id',
        'full_name',
        'email',
        'department',
        'job_title',
        'employment_status',
        'base_salary',
        'joining_date',
        'is_active_employee',
    )
    list_filter = ('employment_status', 'department', 'job_title', 'joining_date')
    search_fields = ('employee_id', 'full_name', 'email', 'phone')
    raw_id_fields = ('user', 'department', 'job_title')
    ordering = ('full_name',)
