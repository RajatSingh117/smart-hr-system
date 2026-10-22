from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'apps.accounts'

    def ready(self):
        from apps.accounts.signals import register_audit_signals
        register_audit_signals()
