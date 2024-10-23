"""
App for 2U-specific edx-platform Datadog monitoring.
"""

import logging

from django.apps import AppConfig

from .code_owner.utils import get_code_owner_from_module

log = logging.getLogger(__name__)


class DatadogMonitoringSpanProcessor:
    """Datadog span processor that adds custom monitoring (e.g. code owner tags)."""

    def on_span_start(self, span):
        if not span or not getattr(span, 'name') or not  getattr(span, 'resource'):
            return

        if span.name == 'celery.run':
            # We can use this for celery spans, because the resource name is more predictable
            # and available from the start. For django requests, we'll instead continue to use
            # django middleware for setting code owner.
            get_code_owner_from_module(span.resource)

    def on_span_finish(self, span):
        pass

    def shutdown(self, _timeout):
        pass


class DatadogMonitoring(AppConfig):
    """
    Django application to handle 2U-specific Datadog monitoring.
    """
    name = 'edx_arch_experiments.datadog_monitoring'

    # Mark this as a plugin app
    plugin_app = {}

    def ready(self):
        try:
            from ddtrace import tracer  # pylint: disable=import-outside-toplevel
            # QUESTION: Do we want to publish a base constraint that avoids DD major changes without first testing them?
            tracer._span_processors.append(DatadogMonitoringSpanProcessor())  # pylint: disable=protected-access
            log.info("Attached DatadogMonitoringSpanProcessor")
        except ImportError:
            log.warning(
                "Unable to attach DatadogMonitoringSpanProcessor"
                " -- ddtrace module not found."
            )
