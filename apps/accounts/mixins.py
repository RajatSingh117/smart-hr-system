"""
Mixin for models that want automatic audit logging.
M3, M4, M5 models should inherit from this mixin.
"""
from django.db import models


class AuditedModelMixin(models.Model):
    """
    Mixin to enable automatic audit logging on model save/delete.
    Models using this mixin will have their changes automatically logged
    via signals when accounts.signals.register_audit_signals() is called.

    Usage:
        class Employee(AuditedModelMixin):
            user = models.ForeignKey(User, ...)
            ...
    """

    class Meta:
        abstract = True

    # These attributes are set by signal handlers during save/delete
    _audit_action = None
    _audit_changes = None
    _audit_request = None
    _audit_actor = None

    def save(self, *args, **kwargs):
        # Allow passing audit context through save()
        audit_request = kwargs.pop('audit_request', None)
        audit_actor = kwargs.pop('audit_actor', None)

        if audit_request:
            self._audit_request = audit_request
        if audit_actor:
            self._audit_actor = audit_actor

        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        # Allow passing audit context through delete()
        audit_request = kwargs.pop('audit_request', None)
        audit_actor = kwargs.pop('audit_actor', None)

        if audit_request:
            self._audit_request = audit_request
        if audit_actor:
            self._audit_actor = audit_actor

        super().delete(*args, **kwargs)