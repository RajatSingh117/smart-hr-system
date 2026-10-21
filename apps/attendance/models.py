from django.conf import settings
from apps.accounts.mixins import AuditedModelMixin


class Attendance(AuditedModelMixin):
    """One attendance record per employee per day."""

    class Status(models.TextChoices):
        PRESENT = "PRESENT", "Present"
        ABSENT = "ABSENT", "Absent"
        LATE = "LATE", "Late"
        HALF_DAY = "HALF_DAY", "Half-day"
        ON_LEAVE = "ON_LEAVE", "On-leave"

    employee = models.ForeignKey(
        "employees.Employee",
        on_delete=models.PROTECT,
        related_name="attendance_records",
    )
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_corrections",
    )
    corrected_at = models.DateTimeField(null=True, blank=True)
    correction_note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date", "employee"]
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"],
                name="uniq_attendance_employee_date",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(check_in__isnull=True)
                    | models.Q(check_out__isnull=True)
                    | models.Q(check_out__gt=models.F("check_in"))
                ),
                name="attendance_checkout_after_checkin",
            ),
        ]
        indexes = [
            models.Index(fields=["date", "status"]),
        ]

    def __str__(self):
        return f"{self.employee} - {self.date} ({self.get_status_display()})"
