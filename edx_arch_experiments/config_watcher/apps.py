"""
App for reporting configuration changes to Slack for operational awareness.
"""

from django.apps import AppConfig


class ConfigWatcher(AppConfig):
    """
    Django application to report configuration changes to operators.
    """
    name = 'edx_arch_experiments.config_watcher'

    # Mark this as a plugin app
    plugin_app = {}

    def ready(self):
        from .signals import receivers  # pylint: disable=import-outside-toplevel

        receivers.connect_receivers()
