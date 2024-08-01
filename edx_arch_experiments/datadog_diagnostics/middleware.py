"""
Diagnostic middleware for Datadog.

To use, install edx-arch-experiments and add
``edx_arch_experiments.datadog_diagnostics.middleware.DatadogDiagnosticMiddleware``
to ``MIDDLEWARE``, then set the below settings as needed.
"""

import logging
import time

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
        local_root_span = self.dd_tracer.current_root_span()

        if DETECT_ANOMALOUS_TRACE.is_enabled():
            root_duration_s = local_root_span.duration
            if root_duration_s is not None:
                worker_run_time_s = time.time() - self.worker_start_epoch
                log.warning(
                    f"Anomalous Datadog local root span (duration already set): "
                    f"id = {local_root_span.trace_id:x}; "
                    f"duration = {root_duration_s:0.3f} sec; "
                    f"worker age = {worker_run_time_s:0.3f} sec"
                )

        if LOG_ROOT_SPAN.is_enabled():
            route_pattern = getattr(request.resolver_match, 'route', None)
            current_span = self.dd_tracer.current_span()
            # pylint: disable=protected-access
            log.info(
                f"Datadog span diagnostics: Route = {route_pattern}; "
                f"local root span = {local_root_span._pprint()}; "
                f"current span = {current_span._pprint()}"
            )
