from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import LeaveRequest, LeaveStatusHistory


@receiver(post_save, sender=LeaveRequest)
def record_initial_leave_history(sender, instance, created, **kwargs):
    if created:
        LeaveStatusHistory.objects.create(
            leave_request=instance,
            old_status="",
            new_status=instance.status,
            changed_by=instance.approver,
            remarks=instance.approver_remarks,
        )