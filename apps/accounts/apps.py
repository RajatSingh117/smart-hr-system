from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'apps.accounts'
    verbose_name = 'User Accounts & Authentication'

    def ready(self):
        # Import signals when app is ready
        import apps.accounts.signals  # noqa