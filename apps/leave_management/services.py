from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from .models import LeaveRequest, LeaveStatusHistory


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