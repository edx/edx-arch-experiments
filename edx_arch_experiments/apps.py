"""
edx_arch_experiments Django application initialization.
"""

from django.apps import AppConfig
from edx_django_utils.plugins.constants import PluginSettings, PluginURLs


class EdxArchExperimentsConfig(AppConfig):
    """
    Configuration for the edx_arch_experiments Django application.
    """

    name = 'edx_arch_experiments'
    plugin_app = {
        PluginSettings.CONFIG: {
            'lms.djangoapp': {
                'common': {
                    PluginSettings.RELATIVE_PATH: 'settings.common',
                },
                'production': {
                    PluginSettings.RELATIVE_PATH: 'settings.production',
                },
            }
        },
        PluginURLs.CONFIG: {
            'lms.djangoapp': {
                PluginURLs.NAMESPACE: 'edx_arch_experiments',
                PluginURLs.REGEX: r'^api/certificates/v1/',
                PluginURLs.RELATIVE_PATH: 'certificates.urls',
            }
        },
    }
