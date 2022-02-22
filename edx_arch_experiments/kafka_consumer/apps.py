"""App for consuming Kafka events. Comprises a management command for listening to a topic and supporting methods.
Likely temporary."""
from django.apps import AppConfig
from edx_django_utils.plugins.constants import PluginSettings


class KafkaConsumerApp(AppConfig):
    name = 'edx_arch_experiments.kafka_consumer'

    """
    Configuration for the edx_arch_experiments Django application.
    """

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
        }
    }

