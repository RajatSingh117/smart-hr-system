"""
Audit logging helper for cross-app audit trail.
Can be imported by M3, M4, M5 to log audit events.
"""

from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.accounts.models import User


def log_audit(actor, action, obj, changes=None, request=None):
    """
    Create an audit log entry.

    Args:
        actor: User who performed the action (None for system actions).
        action: CREATE, UPDATE, DELETE, VIEW, EXPORT, APPROVE, REJECT.
        obj: Model instance being audited.
        changes: Dict of field changes.
        request: Optional HttpRequest for IP and User-Agent.

    Returns:
        AuditEvent instance.
    """
    from apps.accounts.models import AuditEvent

    content_type = ContentType.objects.get_for_model(obj)

    # Serialize field changes
    changes_json = None

    if changes:
        def serialize_val(val):
            if val is None:
                return None
            if isinstance(val, (str, int, float, bool)):
                return val
            if isinstance(val, models.Model):
                return str(val)
            if hasattr(val, "isoformat"):
                return val.isoformat()
            return str(val)

        changes_json = {
            field: {
                "old": serialize_val(change.get("old")),
                "new": serialize_val(change.get("new")),
            }
            for field, change in changes.items()
        }

    # Safe defaults for request-independent calls
    ip_address = None
    user_agent = "Unknown"

    if request is not None:
        meta = request.META

        forwarded_for = meta.get("HTTP_X_FORWARDED_FOR")
        if forwarded_for:
            ip_address = forwarded_for.split(",")[0].strip() or None
        else:
            ip_address = meta.get("REMOTE_ADDR") or None

        # Guarantee a non-null, non-empty value
        user_agent = (meta.get("HTTP_USER_AGENT") or "").strip()[:500]
        user_agent = user_agent or "Unknown"

    audit_event = AuditEvent.objects.create(
        actor=actor,
        action=action,
        content_type=content_type,
        object_id=obj.pk,
        object_repr=str(obj)[:200],
        changes=changes_json,
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return audit_event


class AuditLogger:
    """Context manager for batch audit logging."""

    def __init__(self, actor, request=None):
        self.actor = actor
        self.request = request
        self.entries = []

    def log(self, action, obj, changes=None):
        entry = log_audit(
            actor=self.actor,
            action=action,
            obj=obj,
            changes=changes,
            request=self.request,
        )
        self.entries.append(entry)
        return entry

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Audit entries are saved immediately.
        return False