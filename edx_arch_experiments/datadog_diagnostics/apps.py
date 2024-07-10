"""
App for emitting additional diagnostic information for the Datadog integration.
"""

import logging

from django.apps import AppConfig

log = logging.getLogger(__name__)


class MissingSpanProcessor:
    """Datadog span processor that logs unfinished spans at shutdown."""
    spans_started = 0
    spans_finished = 0
    open_spans = {}

    def on_span_start(self, span):
        self.spans_started += 1
        self.open_spans[span.span_id] = span

    def on_span_finish(self, span):
        self.spans_finished += 1
        del self.open_spans[span.span_id]

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
        try:
            from ddtrace import tracer  # pylint: disable=import-outside-toplevel
            tracer._span_processors.append(MissingSpanProcessor())  # pylint: disable=protected-access
            log.info("Attached MissingSpanProcessor for Datadog diagnostics")
        except ImportError:
            log.warning(
                "Unable to attach MissingSpanProcessor for Datadog diagnostics"
                " -- ddtrace module not found."
            )
