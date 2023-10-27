"""
Signal receivers for the config watcher.

Call ``connect_receivers`` to initialize.
"""

import html
import json
import logging
import urllib.request

import waffle.models
from django.conf import settings
from django.db.models import signals
from django.dispatch import receiver

log = logging.getLogger(__name__)

# .. setting_name: CONFIG_WATCHER_SLACK_WEBHOOK_URL
# .. setting_default: None
# .. setting_description: Slack webhook URL to send config change events to.
#   If not configured, this functionality is disabled.
CONFIG_WATCHER_SLACK_WEBHOOK_URL = getattr(settings, 'CONFIG_WATCHER_SLACK_WEBHOOK_URL', None)


def _send_to_slack(message):
    """Send this message as plain text to the configured Slack channel."""
    if not CONFIG_WATCHER_SLACK_WEBHOOK_URL:
        return

    # https://api.slack.com/reference/surfaces/formatting
    body_data = {
        'text': html.escape(message, quote=False)
    }

    req = urllib.request.Request(
        url=CONFIG_WATCHER_SLACK_WEBHOOK_URL, data=json.dumps(body_data).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        status = resp.getcode()
        if status != 200:
            log.error(f"Slack rejected the config watcher message. {status=}, body={resp.read().decode('utf-8')}")


def _report_config_change(message):
    """
    Report this message string as a configuration change.

    Sends to logs and to Slack.
    """
    log.info(message)
    _send_to_slack(message)


def _report_waffle_change(model_short_name, instance, created, fields):
    """
    Report that a model instance has been created or updated.
    """
    verb = "created" if created else "updated"
    state_desc = ", ".join(f"{field}={repr(getattr(instance, field))}" for field in fields)
    _report_config_change(f"Waffle {model_short_name} {instance.name!r} was {verb}. New config: {state_desc}")


def _report_waffle_delete(model_short_name, instance):
    """
    Report that a model instance has been deleted.
    """
    _report_config_change(f"Waffle {model_short_name} {instance.name!r} was deleted")


# List of models to observe. Each is a dictionary that matches the
# keyword args of _register_waffle_observation.
_WAFFLE_MODELS_TO_OBSERVE = [
    {
        'model': waffle.models.Flag,
        'short_name': 'flag',
        'fields': ['everyone', 'percent', 'note'],
    },
    {
        'model': waffle.models.Switch,
        'short_name': 'switch',
        'fields': ['active', 'note'],
    },
    {
        'model': waffle.models.Sample,
        'short_name': 'sample',
        'fields': ['percent', 'note'],
    },
]


def _register_waffle_observation(*, model, short_name, fields):
    """
    Register a Waffle model for observation according to config values.

    Args:
        model (class): The model class to monitor
        short_name (str): A short descriptive name for an instance of the model, e.g. "flag"
        fields (list): Names of fields to report on in the Slack message
    """
    @receiver(signals.post_save, sender=model)
    def report_waffle_change(*args, instance, created, **kwargs):
        try:
            _report_waffle_change(short_name, instance, created, fields)
        except:  # noqa pylint: disable=bare-except
            # Log and suppress error so Waffle change can proceed
            log.exception(f"Failed to report change to waffle {short_name}")

    @receiver(signals.post_delete, sender=model)
    def report_waffle_delete(*args, instance, **kwargs):
        try:
            _report_waffle_delete(short_name, instance)
        except:  # noqa pylint: disable=bare-except
            log.exception(f"Failed to report deletion of waffle {short_name}")


def connect_receivers():
    """
    Initialize application's receivers.
    """
    for config in _WAFFLE_MODELS_TO_OBSERVE:
        _register_waffle_observation(**config)
