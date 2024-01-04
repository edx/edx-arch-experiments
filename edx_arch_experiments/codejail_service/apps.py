"""
App for running answer submissions inside of codejail.
"""

from django.apps import AppConfig
from edx_django_utils.plugins.constants import PluginURLs


class CodejailService(AppConfig):
    """
    Django application to run things in codejail.
    """
    name = 'edx_arch_experiments.codejail_service'

    plugin_app = {
        PluginURLs.CONFIG: {
            'lms.djangoapp': {
                PluginURLs.NAMESPACE: 'codejail_service',
            }
        },
    }
