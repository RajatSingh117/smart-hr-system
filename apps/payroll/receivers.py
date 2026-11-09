
import logging

from django.dispatch import receiver

from apps.leave_management.models import LeaveRequest
from apps.leave_management.events import (
    leave_decision_made,
    leave_cancelled,
)
from apps.attendance.models import Attendance
from apps.attendance.events import attendance_corrected

from .notifications import send_notification


logger = logging.getLogger(__name__)


def _format_time(value):
    """Format an optional attendance datetime."""
    if value is None:
        return "Not recorded"

    return value.strftime("%I:%M %p")


@receiver(leave_decision_made)
def handle_leave_decision(sender, **kwargs):
    """Send an email when a leave request is approved or rejected."""

    try:
        leave_request = (
            LeaveRequest.objects
            .select_related("employee", "leave_type")
            .get(pk=kwargs["leave_request_id"])
        )

        employee = leave_request.employee

        if not employee.email:
            logger.warning(
                "No email address for employee ID %s",
                employee.pk,
            )
            return

        status = leave_request.get_status_display()

        context = {
            "employee_name": employee.full_name,
            "status": status,
            "start_date": str(leave_request.start_date),
            "end_date": str(leave_request.end_date),
            "remarks": kwargs.get("remarks", ""),
        }

        send_notification(
            notification_name="leave_decision",
            recipient=employee.email,
            context=context,
            subject=f"Leave Request {status}",
        )

    except Exception:
        logger.exception(
            "Failed to process leave decision notification."
        )


@receiver(leave_cancelled)
def handle_leave_cancelled(sender, **kwargs):
    """Notify HR/Admin cancellations, but skip owner cancellations."""

    try:
        if kwargs.get("cancelled_by_owner", False):
            logger.info(
                "Skipping cancellation email initiated by the employee."
            )
            return

        leave_request = (
            LeaveRequest.objects
            .select_related("employee", "leave_type")
            .get(pk=kwargs["leave_request_id"])
        )

        employee = leave_request.employee

        if not employee.email:
            logger.warning(
                "No email address for employee ID %s",
                employee.pk,
            )
            return

        context = {
            "employee_name": employee.full_name,
            "status": "Cancelled",
            "start_date": str(leave_request.start_date),
            "end_date": str(leave_request.end_date),
            "remarks": kwargs.get("remarks", ""),
        }

        send_notification(
            notification_name="leave_decision",
            recipient=employee.email,
            context=context,
            subject="Leave Request Cancelled",
        )

    except Exception:
        logger.exception(
            "Failed to process leave cancellation notification."
        )


@receiver(attendance_corrected)
def handle_attendance_corrected(sender, **kwargs):
    """Send an email when HR corrects an attendance record."""

    try:
        attendance = (
            Attendance.objects
            .select_related("employee")
            .get(pk=kwargs["attendance_id"])
        )

        employee = attendance.employee

        if not employee.email:
            logger.warning(
                "No email address for employee ID %s",
                employee.pk,
            )
            return

        context = {
            "employee_name": employee.full_name,
            "attendance_date": str(attendance.date),
            "status": attendance.get_status_display(),
            "check_in": _format_time(attendance.check_in),
            "check_out": _format_time(attendance.check_out),
        }

        send_notification(
            notification_name="attendance_update",
            recipient=employee.email,
            context=context,
            subject="Attendance Record Updated",
        )

    except Exception:
        logger.exception(
            "Failed to process attendance correction notification."
        )
