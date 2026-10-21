from decimal import Decimal

from django.conf import settings
from django.db import models

# Create your models here.
from decimal import Decimal

from django.conf import settings
from django.db import models


class LeaveType(models.Model):
    """Names of leave kinds. Entered as data; no quotas assumed."""

    name = models.CharField(max_length=100, unique=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveBalance(models.Model):
    """Remaining leave for one employee, leave type and year."""

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.PROTECT,
        related_name="leave_balances",
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name="balances",
    )
    year = models.PositiveSmallIntegerField()
    remaining_days = models.DecimalField(
        max_digits=6, decimal_places=2, default=Decimal("0.00")
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year", "employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "leave_type", "year"],
                name="uniq_leave_balance_employee_type_year",
            ),
        ]

    def __str__(self):
        return f"{self.employee} - {self.leave_type} ({self.year})"


class LeaveRequest(models.Model):
    """One leave application and its current status."""

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"
        CANCELLED = "CANCELLED", "Cancelled"

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.PROTECT,
        related_name="leave_requests",
    )
    leave_type = models.ForeignKey(
        LeaveType,
        on_delete=models.PROTECT,
        related_name="requests",
    )
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_decisions",
    )
    approver_remarks = models.TextField(blank=True)
    decided_at = models.DateTimeField(null=True, blank=True)
    class RestorationStatus(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", "Not required"
        PENDING = "PENDING", "Pending"
        COMPLETED = "COMPLETED", "Completed"
        HR_REVIEW = "HR_REVIEW", "Requires HR review"

    restoration_status = models.CharField(
        max_length=20,
        choices=RestorationStatus.choices,
        default=RestorationStatus.NOT_REQUIRED,
    )
    restoration_review_reason = models.TextField(blank=True)
    restoration_completed_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="leave_end_date_not_before_start",
            ),
        ]
        indexes = [
            models.Index(fields=["employee", "start_date", "end_date"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.employee}: {self.start_date} to {self.end_date} [{self.status}]"


class LeaveStatusHistory(models.Model):
    """One row for every status change of a leave request."""

    leave_request = models.ForeignKey(
        LeaveRequest,
        on_delete=models.PROTECT,
        related_name="history",
    )
    old_status = models.CharField(
        max_length=20, choices=LeaveRequest.Status.choices, blank=True
    )
    new_status = models.CharField(
        max_length=20, choices=LeaveRequest.Status.choices
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="leave_status_changes",
    )
    remarks = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["changed_at", "id"]
        verbose_name_plural = "leave status history"
        indexes = [
            models.Index(fields=["leave_request", "changed_at"]),
        ]

    def __str__(self):
        return f"{self.leave_request_id}: {self.old_status or '-'} to {self.new_status}"


class PublicHoliday(models.Model):
    """A configured public holiday excluded from leave duration."""

    date = models.DateField(unique=True)
    name = models.CharField(max_length=100)

    class Meta:
        ordering = ["date"]

    def __str__(self):
        return f"{self.name} ({self.date})"

        return f"{self.leave_request_id}: {self.old_status or '-'} to {self.new_status}"
