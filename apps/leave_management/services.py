from django.core.exceptions import ValidationError
from django.db import transaction

from .models import LeaveRequest, LeaveStatusHistory


ALLOWED_TRANSITIONS = {
    LeaveRequest.Status.PENDING: {
        LeaveRequest.Status.APPROVED,
        LeaveRequest.Status.REJECTED,
        LeaveRequest.Status.CANCELLED,
    },
}


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
        raise ValidationError("The leave request already has this status.")

    if new_status not in ALLOWED_TRANSITIONS.get(old_status, set()):
        raise ValidationError(
            f"Cannot change leave status from {old_status} to {new_status}."
        )

    leave_request.status = new_status
    leave_request.approver = changed_by
    leave_request.approver_remarks = remarks
    leave_request.save(
        update_fields=[
            "status",
            "approver",
            "approver_remarks",
            "updated_at",
        ]
    )

    LeaveStatusHistory.objects.create(
        leave_request=leave_request,
        old_status=old_status,
        new_status=new_status,
        changed_by=changed_by,
        remarks=remarks,
    )

    return leave_request