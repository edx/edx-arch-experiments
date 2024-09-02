"""
Tests for plugin app.
"""

from unittest.mock import call, patch

import celery.signals
from ddtrace import tracer
from django.dispatch import Signal
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


class TestCeleryLogging(TestCase):
    """
    Tests for celery signal logging.

    While it would be nice to test actual Celery tasks and signals,
    it's difficult to get that all working with unit tests. We'd have
    to use Celery's pytest extra, which provides fixtures, but those
    don't play well with unittest's TestCase classes and even after
    converting to top-level functions things just seemed to hang after
    setup.

    So instead, we'll mock things out at the signal level and just
    ensure that each level of functionality works in isolation.
    """

    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.info')
    def test_default_config_has_no_signals(self, mock_log_info):
        apps.DatadogDiagnostics('edx_arch_experiments.datadog_diagnostics', apps).ready()
        mock_log_info.assert_called_with("Logging lifecycle info for these celery signals: []")

    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.info')
    def test_registration_maximal(self, mock_log_info):
        """Test that all celery signal names are actually signals."""
        all_signal_names = ', '.join(sorted(apps.CELERY_SIGNAL_CONFIG.keys()))
        with override_settings(DATADOG_DIAGNOSTICS_CELERY_LOG_SIGNALS=all_signal_names):
            apps.DatadogDiagnostics('edx_arch_experiments.datadog_diagnostics', apps).ready()

        mock_log_info.assert_called_with(
            "Logging lifecycle info for these celery signals: ['after_task_publish', "
            "'before_task_publish', 'task_failure', 'task_internal_error', "
            "'task_postrun', 'task_prerun', 'task_received', 'task_rejected', "
            "'task_retry', 'task_revoked', 'task_success', 'task_unknown']"
        )

    @override_settings(
        DATADOG_DIAGNOSTICS_CELERY_LOG_SIGNALS=',,,task_success, task_unknown, task_rejected, fake_signal'
    )
    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.info')
    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.warning')
    @patch('edx_arch_experiments.datadog_diagnostics.apps._connect_celery_handler')
    def test_register(self, mock_connect, mock_log_warning, mock_log_info):
        """Test that signal connector is *called* as expected."""

        with patch.dict('edx_arch_experiments.datadog_diagnostics.apps.CELERY_SIGNAL_CONFIG'):
            # Add a bad entry to the config to test the signal lookup path
            apps.CELERY_SIGNAL_CONFIG['fake_signal'] = lambda kwargs: {}
            # Remove a real signal from the config to test the extractor lookup path
            del apps.CELERY_SIGNAL_CONFIG['task_unknown']
            apps.DatadogDiagnostics('edx_arch_experiments.datadog_diagnostics', apps).ready()

        assert mock_connect.call_args_list == [
            call(
                celery.signals.task_success,
                'task_success',
                apps.CELERY_SIGNAL_CONFIG['task_success'],
            ),
            call(
                celery.signals.task_rejected,
                'task_rejected',
                apps.CELERY_SIGNAL_CONFIG['task_rejected'],
            ),
        ]
        assert mock_log_warning.call_args_list == [
            call("Don't know how to extract info for Celery signal 'task_unknown'; ignoring."),
            call("Could not connect receiver to unknown Celery signal 'fake_signal'"),
        ]
        mock_log_info.assert_called_with(
            "Logging lifecycle info for these celery signals: ['task_success', 'task_rejected']"
        )

    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.info')
    @patch('edx_arch_experiments.datadog_diagnostics.apps.log.exception')
    def test_handler(self, mock_log_exception, mock_log_info):
        """Test that signal connector *behaves* as expected."""
        # Signal A will just do a straightforward data extraction from the kwargs.
        # pylint: disable=protected-access
        apps._connect_celery_handler(
            signal_example_a, 'signal_example_a',
            lambda kwargs: {'name': kwargs['info']['name']},
        )

        # Signal B will have an extractor that goes bad on the 2nd and 3rd calls
        b_called_times = 0

        def b_extractor(kwargs):
            nonlocal b_called_times
            b_called_times += 1
            if b_called_times >= 2:
                raise Exception("oops")

            return {'id': kwargs['the_id']}

        # pylint: disable=protected-access
        apps._connect_celery_handler(signal_example_b, 'signal_example_b', b_extractor)

        # Send to B a few times to show that error logging only happens once
        signal_example_b.send(sender='some_sender', the_id=42)
        signal_example_b.send(sender='some_sender', the_id=42)
        signal_example_b.send(sender='some_sender', the_id=42)
        # And then send to A to show it still works
        signal_example_a.send(
            sender='some_sender', other='whatever', info={'name': "Alice"}, name='not this one',
        )

        mock_log_exception.assert_called_once_with(
            "Error while extracting Celery signal info for 'signal_example_b'; "
            "will not attempt for future calls to this signal."
        )
        assert b_called_times == 2
        assert mock_log_info.call_args_list == [
            call("Celery signal called: 'signal_example_b' with name=None id=42"),
            call("Celery signal called: 'signal_example_b' (skipped data extraction)"),
            call("Celery signal called: 'signal_example_b' (skipped data extraction)"),
            call("Celery signal called: 'signal_example_a' with name=Alice id=None"),
        ]


signal_example_a = Signal()
signal_example_b = Signal()
