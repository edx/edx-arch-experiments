"""
App for reporting configuration changes to Slack for operational awareness.
"""

from django.apps import AppConfig


class ConfigWatcherApp(AppConfig):
    """
    Django application to report configuration changes to operators.
    """
    name = 'edx_arch_experiments.config_watcher'

    def ready(self):
        from .signals import receivers  # pylint: disable=import-outside-toplevel

        receivers.connect_receivers()
