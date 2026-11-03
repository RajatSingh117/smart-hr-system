

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .models import NotificationLog


TEMPLATES = {
    "leave_decision": {
        "template": "payroll/emails/leave_decision.html",
        "notification_type": NotificationLog.NotificationType.LEAVE_DECISION,
    },
    "attendance_update": {
        "template": "payroll/emails/attendance_update.html",
        "notification_type": NotificationLog.NotificationType.ATTENDANCE_UPDATE,
    },
    "payslip_ready": {
        "template": "payroll/emails/payslip_ready.html",
        "notification_type": NotificationLog.NotificationType.PAYSLIP_READY,
    },
}


def send_notification(notification_name, recipient, context, subject):
    """
    Render and send an email, then record its delivery status.

    Returns:
        NotificationLog: The notification delivery record.

    SENT means the configured email backend accepted the message.
    FAILED means rendering or sending failed.
    """
    if notification_name not in TEMPLATES:
        raise ValueError(f"Unknown notification type: {notification_name}")

    template_info = TEMPLATES[notification_name]

    log = NotificationLog.objects.create(
        recipient=recipient,
        notification_type=template_info["notification_type"],
        subject=subject,
        status=NotificationLog.Status.PENDING,
    )

    try:
        html_content = render_to_string(
            template_info["template"],
            context,
        )

        email = EmailMultiAlternatives(
            subject=subject,
            body="Please view this email in an HTML-compatible email client.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[recipient],
        )
        email.attach_alternative(html_content, "text/html")

        sent_count = email.send(fail_silently=False)

        if sent_count != 1:
            log.status = NotificationLog.Status.FAILED
            log.error_message = (
                "Email backend did not confirm sending the message."
            )
            log.save(update_fields=["status", "error_message"])
            return log

        log.status = NotificationLog.Status.SENT
        log.sent_at = timezone.now()
        log.error_message = ""
        log.save(
            update_fields=["status", "sent_at", "error_message"]
        )

    except Exception:
        log.status = NotificationLog.Status.FAILED
        log.error_message = "Email rendering or delivery failed."
        log.save(update_fields=["status", "error_message"])

    return log
