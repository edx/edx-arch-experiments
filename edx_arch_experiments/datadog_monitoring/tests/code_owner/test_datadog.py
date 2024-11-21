"""
Tests for datadog span processor.
"""
from unittest.mock import patch

from django.test import TestCase

from edx_arch_experiments.datadog_monitoring.code_owner.datadog import CeleryCodeOwnerSpanProcessor


class FakeSpan:
    """
    A fake Span instance with span name and resource.
    """

    def __init__(self, name, resource):
        self.name = name
        self.resource = resource


class TestCeleryCodeOwnerSpanProcessor(TestCase):
    """
    Tests for CeleryCodeOwnerSpanProcessor.
    """

    @patch('edx_arch_experiments.datadog_monitoring.code_owner.utils.set_custom_attribute')
    def test_celery_span(self, mock_set_custom_attribute):
        """ Tests processor with a celery span. """
        proc = CeleryCodeOwnerSpanProcessor()
        celery_span = FakeSpan('celery.run', 'test.module.for.celery.task')

        proc.on_span_start(celery_span)

        mock_set_custom_attribute.assert_called_once_with('code_owner_2_module', 'test.module.for.celery.task')

    @patch('edx_arch_experiments.datadog_monitoring.code_owner.utils.set_custom_attribute')
    def test_other_span(self, mock_set_custom_attribute):
        """ Tests processor with a non-celery span. """
        proc = CeleryCodeOwnerSpanProcessor()
        celery_span = FakeSpan('other.span', 'test.resource.name')

        proc.on_span_start(celery_span)

        mock_set_custom_attribute.assert_not_called()

    @patch('edx_arch_experiments.datadog_monitoring.code_owner.utils.set_custom_attribute')
    def test_non_span(self, mock_set_custom_attribute):
        """ Tests processor with an object that doesn't have span name or resource. """
        proc = CeleryCodeOwnerSpanProcessor()
        non_span = object()

        proc.on_span_start(non_span)

        mock_set_custom_attribute.assert_not_called()
