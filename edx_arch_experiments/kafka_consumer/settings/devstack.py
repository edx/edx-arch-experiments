import os
from os.path import join, abspath, dirname


def plugin_settings(settings):
    """Devstack settings values."""
    settings.KAFKA_BOOTSTRAP_SERVER = "edx.devstack.kafka:29092"
    settings.SCHEMA_REGISTRY_URL = "http://edx.devstack.schema-registry:8081"
    settings.LICENSE_EVENT_TOPIC_NAME = "license-event-dev"
    if os.path.isfile(join(dirname(abspath(__file__)), 'private.py')):
        from .private import plugin_settings  # pylint: disable=import-error
        plugin_settings(settings)
