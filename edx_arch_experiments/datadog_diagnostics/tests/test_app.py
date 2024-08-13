"""
Tests for plugin app.
"""

from unittest.mock import patch

from ddtrace import tracer
from django.test import TestCase, override_settings

from .. import apps


class FakeSpan:
    """A fake Span instance that just carries a span_id."""
    def __init__(self, span_id):
        self.span_id = span_id

    def _pprint(self):
        return f"span_id={self.span_id}"


class TestMissingSpanProcessor(TestCase):
    """Tests for MissingSpanProcessor."""

    def test_feature_switch(self):
        """
        Regression test -- the use of override_settings ensures that we read
        the setting as needed, and not once at module load time (when it's
        not guaranteed to be available.)
        """
        def initialize():
            apps.DatadogDiagnostics('edx_arch_experiments.datadog_diagnostics', apps).ready()

        def get_processor_list():
            # pylint: disable=protected-access
            return [type(sp).__name__ for sp in tracer._span_processors]

        with override_settings(DATADOG_DIAGNOSTICS_ENABLE=False):
            initialize()
            assert sorted(get_processor_list()) == [
                'EndpointCallCounterProcessor', 'TopLevelSpanProcessor',
            ]

        # The True case needs to come second because the initializer
        # appends to the list and there isn't an immediately obvious
        # way of resetting it.
        with override_settings(DATADOG_DIAGNOSTICS_ENABLE=True):
            initialize()
            assert sorted(get_processor_list()) == [
                'EndpointCallCounterProcessor', 'MissingSpanProcessor', 'TopLevelSpanProcessor',
            ]

    @override_settings(DATADOG_DIAGNOSTICS_MAX_SPANS=3)
    def test_metrics(self):
        proc = apps.MissingSpanProcessor()
        ids = [2, 4, 6, 8, 10]

        for span_id in ids:
            proc.on_span_start(FakeSpan(span_id))

        assert {(sk, sv.span_id) for sk, sv in proc.open_spans.items()} == {(2, 2), (4, 4), (6, 6)}
        assert proc.spans_started == 5
        assert proc.spans_finished == 0

        for span_id in ids:
            proc.on_span_finish(FakeSpan(span_id))

        assert proc.open_spans.keys() == set()
        assert proc.spans_started == 5
        assert proc.spans_finished == 5

    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.info')
    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.error')
    def test_logging(self, mock_log_error, mock_log_info):
        proc = apps.MissingSpanProcessor()
        proc.on_span_start(FakeSpan(17))
        proc.shutdown(0)

        mock_log_info.assert_called_once_with("Spans created = 1; spans finished = 0")
        mock_log_error.assert_called_once_with("Span created but not finished: span_id=17")
