"""
Handlers to listen to celery signals.
"""
import logging

from celery.signals import worker_process_init
from django.dispatch import receiver

from edx_arch_experiments.datadog_monitoring.code_owner.datadog import CeleryCodeOwnerSpanProcessor

log = logging.getLogger(__name__)


@receiver(worker_process_init)
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
