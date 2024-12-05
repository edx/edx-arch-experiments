"""
Handlers to listen to celery signals.
"""
import logging

from celery.signals import worker_process_init
from django.dispatch import receiver
from edx_django_utils.monitoring.signals import (
    monitoring_support_process_exception,
    monitoring_support_process_request,
    monitoring_support_process_response,
)

from edx_arch_experiments.datadog_monitoring.code_owner.datadog import CeleryCodeOwnerSpanProcessor
from edx_arch_experiments.datadog_monitoring.code_owner.utils import set_code_owner_attribute

log = logging.getLogger(__name__)


@receiver(monitoring_support_process_response, dispatch_uid=f"datadog_monitoring_support_process_response")
def datadog_monitoring_support_process_response(sender, request=None, **kwargs):
    """
    Adds datadog monitoring at monitoring process response time.
    """
    if request:
        set_code_owner_attribute(request)
    else:
        log.warning('monitoring_support_process_response sent without '
                    'expected parameter: request.')


@receiver(monitoring_support_process_exception, dispatch_uid=f"datadog_monitoring_support_process_exception")
def datadog_monitoring_support_process_exception(sender, request=None, **kwargs):
    """
    Adds datadog monitoring at monitoring process exception time.
    """
    if request:
        set_code_owner_attribute(request)
    else:
        log.warning('monitoring_support_process_exception sent without '
                    'expected parameter: request.')


@receiver(worker_process_init, dispatch_uid=f"datadog_span_processor_worker_process_init")
def init_worker_process(sender, **kwargs):
    """
    Adds a Datadog span processor to each worker process.

    We have to do this from inside the worker processes because they fork from the
    parent process before the plugin app is initialized.
    """
    try:
        from ddtrace import tracer  # pylint: disable=import-outside-toplevel

        tracer._span_processors.append(CeleryCodeOwnerSpanProcessor())  # pylint: disable=protected-access
        log.info("Attached CeleryCodeOwnerSpanProcessor")
    except ImportError:
        log.warning(
            "Unable to attach CeleryCodeOwnerSpanProcessor"
            " -- ddtrace module not found."
        )
