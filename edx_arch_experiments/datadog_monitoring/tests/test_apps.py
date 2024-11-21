"""
Tests for plugin app.
"""
from celery.signals import worker_process_init
from django.test import TestCase


class TestDatadogMonitoringApp(TestCase):
    """
    Tests for TestDatadogMonitoringApp.
    """

    def test_signal_has_receiver(self):
        """
        Imperfect test to ensure celery signal has the receiver.

        The receiver gets added during DatadogMonitoringApp's ready() call
        at load time. An attempt to disconnect the receiver did not allow it
        to be re-added during a call to ready, presumably because the signal
        was already imported.
        """
        # the name of the function is in the weakref __repr__
        assert 'init_worker_process' in repr(worker_process_init.receivers[0][1])
