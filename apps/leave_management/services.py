from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from .models import LeaveBalance, LeaveRequest, LeaveStatusHistory, PublicHoliday


ALLOWED_TRANSITIONS = {
    LeaveRequest.Status.PENDING: {
        LeaveRequest.Status.APPROVED,
        LeaveRequest.Status.REJECTED,
        LeaveRequest.Status.CANCELLED,
    },
}

BLOCKING_LEAVE_STATUSES = [
    LeaveRequest.Status.PENDING,
    LeaveRequest.Status.APPROVED,
]


def calculate_working_days(start_date, end_date):
    """
    Count working days inclusively, excluding weekends
    and configured public holidays.
    """

    if start_date > end_date:
        raise ValidationError(
            "Leave end date cannot be before the start date."
        )

    holidays = set(
        PublicHoliday.objects.filter(
            date__range=(start_date, end_date)
        ).values_list("date", flat=True)
    )

    working_days = 0
    current_date = start_date

    while current_date <= end_date:
        # weekday(): Monday = 0, Sunday = 6
        is_weekday = current_date.weekday() < 5
        is_public_holiday = current_date in holidays

        if is_weekday and not is_public_holiday:
            working_days += 1

        current_date += timedelta(days=1)

    return working_days

def calculate_working_days_by_year(start_date, end_date):
    """Return working-day counts grouped by calendar year."""

    if start_date > end_date:
        raise ValidationError(
            "Leave end date cannot be before the start date."
        )

    yearly_days = {}
    current_year = start_date.year

    while current_year <= end_date.year:
        year_start = max(
            start_date,
            date(current_year, 1, 1),
        )
        year_end = min(
            end_date,
            date(current_year, 12, 31),
        )

        yearly_days[current_year] = calculate_working_days(
            year_start,
            year_end,
        )

        current_year += 1

    return yearly_days
@transaction.atomic
def create_leave_request(
    employee,
    leave_type,
    start_date,
    end_date,
    reason="",
):
    """Validate and create a leave application."""

    if start_date > end_date:
        raise ValidationError(
            "Leave end date cannot be before the start date."
        )

    overlapping_request = LeaveRequest.objects.filter(
        employee=employee,
        status__in=BLOCKING_LEAVE_STATUSES,
        start_date__lte=end_date,
        end_date__gte=start_date,
    ).exists()

    if overlapping_request:
        raise ValidationError(
            "You already have a pending or approved leave "
            "request overlapping these dates."
        )

    return LeaveRequest.objects.create(
        employee=employee,
        leave_type=leave_type,
        start_date=start_date,
        end_date=end_date,
        reason=reason,
    )


def deduct_leave_balance(leave_request):
    """Deduct leave only when every year's balance is sufficient."""

    yearly_days = calculate_working_days_by_year(
        leave_request.start_date,
        leave_request.end_date,
    )

    balances = []

    # First, validate every year's balance.
    for year, days in yearly_days.items():
        if days == 0:
            continue

        balance = (
            LeaveBalance.objects.select_for_update()
            .filter(
                employee=leave_request.employee,
                leave_type=leave_request.leave_type,
                year=year,
            )
            .first()
        )

        if balance is None or balance.remaining_days < days:
            return False

        balances.append((balance, days))

    # Deduct only after all years pass validation.
    for balance, days in balances:
        balance.remaining_days -= days
        balance.save(
            update_fields=["remaining_days", "updated_at"]
        )

    return True

@transaction.atomic
def change_leave_status(
    leave_request_id,
    new_status,
    changed_by=None,
    remarks="",
):
    leave_request = (
        LeaveRequest.objects.select_for_update()
        .get(pk=leave_request_id)
    )

    old_status = leave_request.status

    if new_status == old_status:
        raise ValidationError(
            "The leave request already has this status."
        )

    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise ValidationError(
            f"Cannot change leave status from {old_status} "
            f"to {new_status}."
        )

    if new_status == LeaveRequest.Status.APPROVED:
        if not deduct_leave_balance(leave_request):
            new_status = LeaveRequest.Status.REJECTED
            remarks = (
                f"{remarks} Insufficient leave balance."
            ).strip()

    leave_request.status = new_status
    leave_request.approver = changed_by
    leave_request.approver_remarks = remarks

    update_fields = [
        "status",
        "approver",
        "approver_remarks",
        "updated_at",
    ]

    if new_status in {
        LeaveRequest.Status.APPROVED,
        LeaveRequest.Status.REJECTED,
    }:
        leave_request.decided_at = timezone.now()
        update_fields.append("decided_at")

    leave_request.save(update_fields=update_fields)

    LeaveStatusHistory.objects.create(
        leave_request=leave_request,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        remarks=remarks,
    )

    return leave_request