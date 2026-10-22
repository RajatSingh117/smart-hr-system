from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.accounts.mixins import AuditedModelMixin


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        HR = "HR", "HR"
        EMPLOYEE = "EMPLOYEE", "Employee"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.EMPLOYEE)

    def get_initials(self):
        """Return user initials for avatar display."""
        if self.first_name and self.last_name:
            return f"{self.first_name[0]}{self.last_name[0]}".upper()
        elif self.first_name:
            return self.first_name[0].upper()
        elif self.email:
            return self.email[0].upper()
        return "U"


class AuditEvent(models.Model):
    """
    Cross-app audit trail. Records who did what to which object.
    M2 Week 2 deliverable — imported by M3, M4, M5 for mutation logging.
    """

    class Action(models.TextChoices):
        CREATE = "CREATE", "Create"
        UPDATE = "UPDATE", "Update"
        DELETE = "DELETE", "Delete"
        VIEW = "VIEW", "View"
        EXPORT = "EXPORT", "Export"
        APPROVE = "APPROVE", "Approve"
        REJECT = "REJECT", "Reject"

    actor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
        help_text="User who performed the action (null for system actions)",
    )
    action = models.CharField(max_length=10, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.BigIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")
    object_repr = models.CharField(max_length=200)
    changes = models.JSONField(null=True, blank=True, help_text="Field diffs: {field: {'old': ..., 'new': ...}}")
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["content_type", "object_id"], name="audit_obj_idx"),
            models.Index(fields=["actor", "timestamp"], name="audit_actor_ts_idx"),
        ]
        verbose_name = "Audit Event"
        verbose_name_plural = "Audit Events"

    def __str__(self):
        return f"{self.timestamp:%Y-%m-%d %H:%M} — {self.actor} {self.action} {self.object_repr}"


class TestAuditedModel(AuditedModelMixin):
    """Test model for audit signal testing (test-only)."""

    name = models.CharField(max_length=100)

    class Meta:
        app_label = 'accounts'

    def __str__(self):
        return self.name