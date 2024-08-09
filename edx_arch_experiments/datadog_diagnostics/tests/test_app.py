"""
Tests for plugin app.
"""

from unittest.mock import call, patch

from django.test import TestCase

from .. import apps


class FakeSpan:
    """A fake Span instance that just carries a span_id."""
    def __init__(self, span_id):
        self.span_id = span_id

    def _pprint(self):
        return f"span_id={self.span_id}"


class TestMissingSpanProcessor(TestCase):
    """Tests for MissingSpanProcessor."""

    @patch.object(apps, 'DATADOG_DIAGNOSTICS_MAX_SPANS', new=3)
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

        assert mock_log_info.call_args_list == [
            call("Early span-start sample: span_id=17"),
            call("Spans created = 1; spans finished = 0"),
        ]
        mock_log_error.assert_called_once_with("Span created but not finished: span_id=17")

    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.info')
    def test_early_span_logging_cutoff(self, mock_log_info):
        with patch('edx_arch_experiments.datadog_diagnostics.apps.time.time', side_effect=[
                # Setup
                1700000000,
                # Span-start time checks
                1700000020,
                1700000040,
                1700010000,
        ]):
            proc = apps.MissingSpanProcessor()
            # Three spans are started
            proc.on_span_start(FakeSpan(44))
            proc.on_span_start(FakeSpan(45))
            proc.on_span_start(FakeSpan(46))

        # Just two early span-starts are logged
        assert mock_log_info.call_args_list == [
            call("Early span-start sample: span_id=44"),
            call("Early span-start sample: span_id=45"),
        ]
