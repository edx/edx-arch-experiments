"""
Tests for celery signal handler.
"""
from unittest.mock import patch

from ddtrace import tracer
from django.test import TestCase

from edx_arch_experiments.datadog_monitoring.signals.handlers import (
    datadog_monitoring_support_process_exception,
    datadog_monitoring_support_process_response,
    init_worker_process,
)


class TestHandlers(TestCase):
    """Tests for signal handlers."""

    def setUp(self):
        # Remove custom span processor from previous runs.
        # pylint: disable=protected-access
        tracer._span_processors = [
            sp for sp in tracer._span_processors if type(sp).__name__ != 'CeleryCodeOwnerSpanProcessor'
        ]

    @patch('edx_arch_experiments.datadog_monitoring.signals.handlers.set_code_owner_attribute')
    def test_datadog_monitoring_support_process_response(self, mock_set_code_owner_attribute):
        datadog_monitoring_support_process_response(sender=None, request='fake request')
        mock_set_code_owner_attribute.assert_called_once_with('fake request')

    @patch('edx_arch_experiments.datadog_monitoring.signals.handlers.set_code_owner_attribute')
    def test_datadog_monitoring_support_process_exception(self, mock_set_code_owner_attribute):
        datadog_monitoring_support_process_exception(sender=None, request='fake request')
        mock_set_code_owner_attribute.assert_called_once_with('fake request')

    def test_init_worker_process(self):
        def get_processor_list():
            # pylint: disable=protected-access
            return [type(sp).__name__ for sp in tracer._span_processors]

        assert sorted(get_processor_list()) == [
            'EndpointCallCounterProcessor', 'TopLevelSpanProcessor',
        ]

        init_worker_process(sender=None)

        assert sorted(get_processor_list()) == [
            'CeleryCodeOwnerSpanProcessor', 'EndpointCallCounterProcessor', 'TopLevelSpanProcessor',
        ]
