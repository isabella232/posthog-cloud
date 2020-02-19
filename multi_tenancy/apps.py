from django.apps import AppConfig
import posthoganalytics # type: ignore


class MultiTenancyConfig(AppConfig):
    name = 'multi_tenancy'
    verbose_name = "MultiTenancy"