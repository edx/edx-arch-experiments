"""
Tests for plugin app.
"""
from unittest.mock import patch

from ddtrace import tracer
from django.test import TestCase

from .. import apps


class FakeSpan:
    """A fake Span instance with span name and resource."""
    def __init__(self, name, resource):
        self.name = name
        self.resource = resource


class TestDatadogMonitoringApp(TestCase):
    """Tests for TestDatadogMonitoringApp."""

    def setUp(self):
        # Remove custom span processor from previous runs.
        # pylint: disable=protected-access
        tracer._span_processors = [
            sp for sp in tracer._span_processors if type(sp).__name__ != 'DatadogMonitoringSpanProcessor'
        ]

    def test_add_processor(self):
        def initialize():
            apps.DatadogMonitoring('edx_arch_experiments.datadog_monitoring', apps).ready()

        def get_processor_list():
            # pylint: disable=protected-access
            return [type(sp).__name__ for sp in tracer._span_processors]

        initialize()
        assert sorted(get_processor_list()) == [
            'DatadogMonitoringSpanProcessor', 'EndpointCallCounterProcessor', 'TopLevelSpanProcessor',
        ]


class TestDatadogMonitoringSpanProcessor(TestCase):
    """Tests for DatadogMonitoringSpanProcessor."""

    @patch('edx_arch_experiments.datadog_monitoring.apps.get_code_owner_from_module')
    def test_celery_span(self, mock_get_code_owner):
        """ Tests processor with a celery span. """
        proc = apps.DatadogMonitoringSpanProcessor()
        celery_span = FakeSpan('celery.run', 'test.module.for.celery.task')

        proc.on_span_start(celery_span)

        mock_get_code_owner.assert_called_once_with('test.module.for.celery.task')

    @patch('edx_arch_experiments.datadog_monitoring.apps.get_code_owner_from_module')
    def test_other_span(self, mock_get_code_owner):
        """ Tests processor with a non-celery span. """
        proc = apps.DatadogMonitoringSpanProcessor()
        celery_span = FakeSpan('other.span', 'test.resource.name')

        proc.on_span_start(celery_span)

        mock_get_code_owner.assert_not_called()

    @patch('edx_arch_experiments.datadog_monitoring.apps.get_code_owner_from_module')
    def test_non_span(self, mock_get_code_owner):
        """ Tests processor with an object that doesn't have span name or resource. """
        proc = apps.DatadogMonitoringSpanProcessor()
        non_span = object()

        proc.on_span_start(non_span)

        mock_get_code_owner.assert_not_called()
