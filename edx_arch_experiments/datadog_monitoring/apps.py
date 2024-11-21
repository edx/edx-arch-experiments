"""
App for 2U-specific edx-platform Datadog monitoring.
"""
from django.apps import AppConfig


class DatadogMonitoring(AppConfig):
    """
    Django application to handle 2U-specific Datadog monitoring.
    """
    name = 'edx_arch_experiments.datadog_monitoring'

    # Mark this as a plugin app
    plugin_app = {}

    def ready(self):
        # Implicitly connect signal handlers decorated with @receiver
        # pylint: disable=import-outside-toplevel,unused-import
        from edx_arch_experiments.datadog_monitoring.signals import handlers
