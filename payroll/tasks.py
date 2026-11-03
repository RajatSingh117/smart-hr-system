from celery import shared_task

from .notifications import send_notification


@shared_task
def send_notification_task(
    notification_name,
    recipient,
    context,
    subject,
):
    """
    Send an email notification asynchronously using Celery.
    """
    log = send_notification(
        notification_name=notification_name,
        recipient=recipient,
        context=context,
        subject=subject,
    )

    return {
        "notification_id": log.pk,
        "status": log.status,
    }