"""
Diagnostic middleware for Datadog.

To use, install edx-arch-experiments and add
``edx_arch_experiments.datadog_diagnostics.middleware.DatadogDiagnosticMiddleware``
to ``MIDDLEWARE``, then set the below settings as needed.
"""

import logging
import time

from django.conf import settings
from django.core.exceptions import MiddlewareNotUsed
from edx_toggles.toggles import WaffleFlag

log = logging.getLogger(__name__)

# .. toggle_name: datadog.diagnostics.detect_anomalous_trace
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables logging of anomalous Datadog traces for web requests.
# .. toggle_warning: This is a noisy feature and so it should only be enabled
#   for a percentage of requests.
# .. toggle_use_cases: temporary
# .. toggle_creation_date: 2024-08-01
# .. toggle_target_removal_date: 2024-11-01
# .. toggle_tickets: https://github.com/edx/edx-arch-experiments/issues/692
DETECT_ANOMALOUS_TRACE = WaffleFlag('datadog.diagnostics.detect_anomalous_trace', module_name=__name__)

# .. toggle_name: datadog.diagnostics.log_root_span
# .. toggle_implementation: WaffleFlag
# .. toggle_default: False
# .. toggle_description: Enables logging of Datadog root span IDs for web requests.
# .. toggle_warning: This is a noisy feature and so it should only be enabled
#   for a percentage of requests.
# .. toggle_use_cases: temporary
# .. toggle_creation_date: 2024-07-24
# .. toggle_target_removal_date: 2024-10-01
# .. toggle_tickets: https://github.com/edx/edx-arch-experiments/issues/692
LOG_ROOT_SPAN = WaffleFlag('datadog.diagnostics.log_root_span', module_name=__name__)


# pylint: disable=missing-function-docstring
class DatadogDiagnosticMiddleware:
    """
    Middleware to add diagnostic logging for Datadog.

    Best added early in the middleware stack.

    Only activates if ``ddtrace`` package is installed and
    ``datadog.diagnostics.log_root_span`` Waffle flag is enabled.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.error = False

        try:
            from ddtrace import tracer  # pylint: disable=import-outside-toplevel
            self.dd_tracer = tracer
        except ImportError:
            # If import fails, don't even load this middleware.
            raise MiddlewareNotUsed  # pylint: disable=raise-missing-from

        self.worker_start_epoch = time.time()
        # .. setting_name: DATADOG_DIAGNOSTICS_LOG_SPAN_DEPTH
        # .. setting_default: 10
        # .. setting_description: Controls how many ancestors spans are logged
        #   when anomalous traces are detected. This limits log size when very
        #   deep span trees are present (such as in anomalous traces, or even
        #   just when each middleware is given a span).
        self.log_span_ancestors_depth = getattr(settings, "DATADOG_DIAGNOSTICS_LOG_SPAN_DEPTH", 10)

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, _view_func, _view_args, _view_kwargs):
        try:
            self.log_diagnostics(request)
        except BaseException as e:
            # If there's an error, it will probably hit every request,
            # so let's just log it once.
            if not self.error:
                self.error = True
                log.error(
                    "Encountered error in DatadogDiagnosticMiddleware "
                    f"(suppressing further errors): {e!r}"
                )

    def log_diagnostics(self, request):
        """
        Contains all the actual logging logic.
        """
        current_span = self.dd_tracer.current_span()
        local_root_span = self.dd_tracer.current_root_span()

        if DETECT_ANOMALOUS_TRACE.is_enabled():
            # For testing, uncomment this line to fake an anomalous span:
            # local_root_span.finish()
            root_duration_s = local_root_span.duration
            if root_duration_s is not None:
                self.log_anomalous_trace(current_span, local_root_span)

        if LOG_ROOT_SPAN.is_enabled():
            route_pattern = getattr(request.resolver_match, 'route', None)
            # pylint: disable=protected-access
            log.info(
                f"Datadog span diagnostics: Route = {route_pattern}; "
                f"local root span = {local_root_span._pprint()}; "
                f"current span = {current_span._pprint()}"
            )

    def log_anomalous_trace(self, current_span, local_root_span):
        worker_run_time_s = time.time() - self.worker_start_epoch

        # Build up a list of spans from current back towards the root, up to a limit.
        ancestors = []
        walk_span = current_span
        while len(ancestors) < self.log_span_ancestors_depth and walk_span is not None:
            ancestors.insert(0, walk_span._pprint())  # pylint: disable=protected-access
            walk_span = walk_span._parent  # pylint: disable=protected-access

        trunc = "(ancestors truncated)\n" if walk_span else ""

        if local_root_span.duration:
            duration_msg = f"duration={local_root_span.duration:0.3f}"
        else:
            # Should only occur during local testing of this
            # middleware, when forcing this code path to run.
            duration_msg = "duration not set"

        msg = (
            "Anomalous Datadog local root span: "
            f"trace_id={local_root_span.trace_id:x}; "
            f"{duration_msg}; "
            f"worker_age={worker_run_time_s:0.3f}; span ancestry:"
        )

        log.warning(msg + "\n" + trunc + "\n".join(ancestors))  # pylint: disable=logging-not-lazy
