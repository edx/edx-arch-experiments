"""Config for summary hook xblock aside"""
from django.apps import AppConfig
from edx_django_utils.plugins.constants import PluginSettings


class SummaryHookConfig(AppConfig):
    """
    Configuration for the Summary Hook xblock aside.
    """

    name = 'edx_arch_experiments.summaryhook_aside'

    plugin_app = {
        PluginSettings.CONFIG: {
            'lms.djangoapp': {
                'common': {
                    PluginSettings.RELATIVE_PATH: 'settings.common',
                },
                'devstack': {
                    PluginSettings.RELATIVE_PATH: 'settings.devstack',
                },
                'production': {
                    PluginSettings.RELATIVE_PATH: 'settings.production',
                },
            }
        }
    }
