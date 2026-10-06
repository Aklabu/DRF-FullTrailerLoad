from django.apps import AppConfig
from django.contrib import admin


class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    label = 'accounts'

    def ready(self):
        import apps.accounts.signals  # noqa: F401
        admin.site.site_header = 'FullTrailerLoad Admin'
        admin.site.site_title = 'FTL Admin'
        admin.site.index_title = 'Platform Administration'
