"""
App for emitting additional diagnostic information for the Datadog integration.
"""

import logging

from django.apps import AppConfig
from django.conf import settings

log = logging.getLogger(__name__)


# .. toggle_name: DATADOG_DIAGNOSTICS_ENABLE
# .. toggle_implementation: DjangoSetting
# .. toggle_default: True
# .. toggle_description: Enables logging of Datadog diagnostics information.
# .. toggle_use_cases: circuit_breaker
# .. toggle_creation_date: 2024-07-11
# .. toggle_tickets: https://github.com/edx/edx-arch-experiments/issues/692
DATADOG_DIAGNOSTICS_ENABLE = getattr(settings, 'DATADOG_DIAGNOSTICS_ENABLE', True)

# .. setting_name: DATADOG_DIAGNOSTICS_MAX_SPANS
# .. setting_default: 100
# .. setting_description: Limit of how many spans to hold onto and log
#   when diagnosing Datadog tracing issues. This limits memory consumption
#   avoids logging more data than is actually needed for diagnosis.
DATADOG_DIAGNOSTICS_MAX_SPANS = getattr(settings, 'DATADOG_DIAGNOSTICS_MAX_SPANS', 100)


class MissingSpanProcessor:
    """Datadog span processor that logs unfinished spans at shutdown."""

    def __init__(self):
        self.spans_started = 0
        self.spans_finished = 0
        self.open_spans = {}

    def on_span_start(self, span):
        self.spans_started += 1
        if len(self.open_spans) < DATADOG_DIAGNOSTICS_MAX_SPANS:
            self.open_spans[span.span_id] = span

    def on_span_finish(self, span):
        self.spans_finished += 1
        self.open_spans.pop(span.span_id, None)  # "delete if present"

    def shutdown(self, _timeout):
        log.info(f"Spans created = {self.spans_started}; spans finished = {self.spans_finished}")
        for span in self.open_spans.values():
            log.error(f"Span created but not finished: {span._pprint()}")  # pylint: disable=protected-access


class DatadogDiagnostics(AppConfig):
    """
    Django application to log diagnostic information for Datadog.
    """
    name = 'edx_arch_experiments.datadog_diagnostics'

    # Mark this as a plugin app
    plugin_app = {}

    def ready(self):
        if not DATADOG_DIAGNOSTICS_ENABLE:
            return

        try:
            from ddtrace import tracer  # pylint: disable=import-outside-toplevel
            tracer._span_processors.append(MissingSpanProcessor())  # pylint: disable=protected-access
            log.info("Attached MissingSpanProcessor for Datadog diagnostics")
        except ImportError:
            log.warning(
                "Unable to attach MissingSpanProcessor for Datadog diagnostics"
                " -- ddtrace module not found."
            )
