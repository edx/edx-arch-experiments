"""
App for emitting additional diagnostic information for the Datadog integration.
"""

import logging
import re

from django.apps import AppConfig
from django.conf import settings

log = logging.getLogger(__name__)


# pylint: disable=missing-function-docstring
class MissingSpanProcessor:
    """Datadog span processor that logs unfinished spans at shutdown."""

    def __init__(self):
        self.spans_started = 0
        self.spans_finished = 0
        self.open_spans = {}

        # .. setting_name: DATADOG_DIAGNOSTICS_MAX_SPANS
        # .. setting_default: 100
        # .. setting_description: Limit of how many spans to hold onto and log
        #   when diagnosing Datadog tracing issues. This limits memory consumption
        #   avoids logging more data than is actually needed for diagnosis.
        self.DATADOG_DIAGNOSTICS_MAX_SPANS = getattr(settings, 'DATADOG_DIAGNOSTICS_MAX_SPANS', 100)

    def on_span_start(self, span):
        self.spans_started += 1
        if len(self.open_spans) < self.DATADOG_DIAGNOSTICS_MAX_SPANS:
            self.open_spans[span.span_id] = span

    def on_span_finish(self, span):
        self.spans_finished += 1
        self.open_spans.pop(span.span_id, None)  # "delete if present"

    def shutdown(self, _timeout):
        log.info(f"Spans created = {self.spans_started}; spans finished = {self.spans_finished}")
        for span in self.open_spans.values():
            log.error(f"Span created but not finished: {span._pprint()}")  # pylint: disable=protected-access


# Dictionary of Celery signal names to a task information extractor.
# The latter is a lambda accepting the signal receiver's kwargs dict
# and returning a minimal dict of info for tracking task lifecycle.
# Celery signal params vary quite a bit in how they convey the
# information we need, so this is probably better than trying to use
# one set of heuristics to get the task ID and name from all signals.
#
# Docs: https://docs.celeryq.dev/en/stable/userguide/signals.html
CELERY_SIGNAL_CONFIG = {
    'before_task_publish': lambda kwargs: {'name': kwargs['sender']},
    'after_task_publish': lambda kwargs: {'name': kwargs['sender']},
    'task_prerun': lambda kwargs: {'name': kwargs['task'].name, 'id': kwargs['task_id']},
    'task_postrun': lambda kwargs: {'name': kwargs['task'].name, 'id': kwargs['task_id']},
    'task_retry': lambda kwargs: {'name': kwargs['sender'].name, 'id': kwargs['request'].id},
    'task_success': lambda kwargs: {'name': kwargs['sender'].name},
    'task_failure': lambda kwargs: {'name': kwargs['sender'].name, 'id': kwargs['task_id']},
    'task_internal_error': lambda kwargs: {'name': kwargs['sender'].name, 'id': kwargs['task_id']},
    'task_received': lambda kwargs: {'name': kwargs['request'].name, 'id': kwargs['request'].id},
    'task_revoked': lambda kwargs: {'name': kwargs['sender'].name, 'id': kwargs['request'].id},
    'task_unknown': lambda kwargs: {'name': kwargs['name'], 'id': kwargs['id']},
    'task_rejected': lambda _kwargs: {},
}


def _connect_celery_handler(signal, signal_name, extractor):
    """
    Register one Celery signal receiver.

    This serves as a closure to capture the config (and some state) for one signal.
    If the extractor ever throws, log the error just once and don't try calling it
    again for the remaining life of the process (as it will likely continue failing
    the same way.)

    Args:
        signal: Django Signal instance to register a handler for
        signal_name: Name of signal in Celery signals module (used for logging)
        extractor: Function to take signal receiver's entire kwargs and return
            a dict optionally containing 'id' and 'name' keys.
    """
    errored = False

    def log_celery_signal(**kwargs):
        nonlocal errored
        info = None
        try:
            if not errored:
                info = extractor(kwargs)
        except BaseException:
            errored = True
            log.exception(
                f"Error while extracting Celery signal info for '{signal_name}'; "
                "will not attempt for future calls to this signal."
            )

        if info is None:
            extra = "(skipped data extraction)"
        else:
            extra = f"with name={info.get('name')} id={info.get('id')}"
        log.info(f"Celery signal called: '{signal_name}' {extra}")

    signal.connect(log_celery_signal, weak=False)


def connect_celery_logging():
    """
    Set up logging of configured Celery signals.

    Throws if celery is not installed.
    """
    import celery.signals  # pylint: disable=import-outside-toplevel

    # .. setting_name: DATADOG_DIAGNOSTICS_CELERY_LOG_SIGNALS
    # .. setting_default: ''
    # .. setting_description: Log calls to these Celery signals (signal name as well
    #   as task name and id, if available). Specify as a comma and/or whitespace delimited
    #   list of names from the celery.signals module. Full list of available signals:
    #   "after_task_publish, before_task_publish, task_failure, task_internal_error,
    #   task_postrun, task_prerun, task_received, task_rejected, task_retry,
    #   task_revoked, task_success, task_unknown"
    DATADOG_DIAGNOSTICS_CELERY_LOG_SIGNALS = getattr(
        settings,
        'DATADOG_DIAGNOSTICS_CELERY_LOG_SIGNALS',
        ''
    )

    connected_names = []
    for signal_name in re.split(r'[,\s]+', DATADOG_DIAGNOSTICS_CELERY_LOG_SIGNALS):
        if not signal_name:  # artifacts from splitting
            continue

        signal = getattr(celery.signals, signal_name, None)
        if not signal:
            log.warning(f"Could not connect receiver to unknown Celery signal '{signal_name}'")
            continue

        extractor = CELERY_SIGNAL_CONFIG.get(signal_name)
        if not extractor:
            log.warning(f"Don't know how to extract info for Celery signal '{signal_name}'; ignoring.")
            continue

        _connect_celery_handler(signal, signal_name, extractor)
        connected_names.append(signal_name)

    log.info(f"Logging lifecycle info for these celery signals: {connected_names!r}")


class DatadogDiagnostics(AppConfig):
    """
    Django application to log diagnostic information for Datadog.
    """
    name = 'edx_arch_experiments.datadog_diagnostics'

    # Mark this as a plugin app
    plugin_app = {}

    def ready(self):
        # .. toggle_name: DATADOG_DIAGNOSTICS_ENABLE
        # .. toggle_implementation: DjangoSetting
        # .. toggle_default: True
        # .. toggle_description: Enables logging of Datadog diagnostics information.
        # .. toggle_use_cases: circuit_breaker
        # .. toggle_creation_date: 2024-07-11
        # .. toggle_tickets: https://github.com/edx/edx-arch-experiments/issues/692
        DATADOG_DIAGNOSTICS_ENABLE = getattr(settings, 'DATADOG_DIAGNOSTICS_ENABLE', True)

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

        # We think that something related to Celery instrumentation is involved
        # in causing trace concatenation in Datadog. DD Support has requested that
        # we log lifecycle information of Celery tasks to see if all of the needed
        # signals are being emitted for their span construction.
        try:
            connect_celery_logging()
        except BaseException:
            log.exception("Unable to subscribe to Celery task signals")
