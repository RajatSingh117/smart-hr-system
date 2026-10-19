"""
Signal handlers for audit logging.
Will be connected in Week 2 when M3/M4/M5 models are available.
"""
from django.db.models.signals import pre_save, post_delete
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType

from apps.accounts.audit import log_audit
from apps.accounts.mixins import AuditedModelMixin


def register_audit_signals():
    """
    Register audit signals for models that use AuditedModelMixin.
    Called from AppConfig.ready() after all models are loaded.
    """
    from django.apps import apps

    for model in apps.get_models():
        if issubclass(model, AuditedModelMixin) and model is not AuditedModelMixin:
            # Connect signals for this model
            pre_save.connect(create_audit_pre_save(model), sender=model, weak=False)
            post_delete.connect(create_audit_post_delete(model), sender=model, weak=False)


def create_audit_pre_save(model):
    """Create pre_save signal handler for a model."""
    def handler(sender, instance, **kwargs):
        if instance.pk is None:
            # New object - will be logged on post_save
            instance._audit_action = 'CREATE'
            instance._audit_changes = None
        else:
            # Existing object - capture changes
            try:
                old_instance = sender.objects.get(pk=instance.pk)
                changes = {}
                for field in instance._meta.fields:
                    if field.name not in ['id', 'created_at', 'updated_at']:
                        old_value = getattr(old_instance, field.name)
                        new_value = getattr(instance, field.name)
                        if old_value != new_value:
                            changes[field.name] = {'old': old_value, 'new': new_value}
                instance._audit_action = 'UPDATE'
                instance._audit_changes = changes if changes else None
            except sender.DoesNotExist:
                instance._audit_action = 'CREATE'
                instance._audit_changes = None
    return handler


def create_audit_post_delete(model):
    """Create post_delete signal handler for a model."""
    def handler(sender, instance, **kwargs):
        # Log deletion
        request = getattr(instance, '_audit_request', None)
        log_audit(
            actor=getattr(instance, '_audit_actor', None),
            action='DELETE',
            obj=instance,
            request=request
        )
    return handler


# Signal to log audit after save (for CREATE and UPDATE)
from django.db.models.signals import post_save

@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    """Log audit after model save if it uses AuditedModelMixin."""
    if isinstance(instance, AuditedModelMixin):
        action = getattr(instance, '_audit_action', 'CREATE' if created else 'UPDATE')
        changes = getattr(instance, '_audit_changes', None)
        request = getattr(instance, '_audit_request', None)
        actor = getattr(instance, '_audit_actor', None)

        if action in ['CREATE', 'UPDATE'] and (changes or action == 'CREATE'):
            log_audit(
                actor=actor,
                action=action,
                obj=instance,
                changes=changes,
                request=request
            )