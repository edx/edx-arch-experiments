"""
Tests for diagnostic middleware.
"""

import re
from contextlib import ExitStack
from unittest.mock import Mock, patch

import ddt
import ddtrace
from django.test import TestCase, override_settings

from ..middleware import CLOSE_ANOMALOUS_SPANS, DETECT_ANOMALOUS_TRACE, LOG_ROOT_SPAN, DatadogDiagnosticMiddleware


def fake_view(_request):
    """Fake get_response for middleware."""


@ddt.ddt
class TestDatadogDiagnosticMiddleware(TestCase):
    """Tests for DatadogDiagnosticMiddleware."""

    def make_middleware(self):
        """Make an instance of the middleware with current settings."""
        return DatadogDiagnosticMiddleware(fake_view)

    def run_middleware(self, middleware=None, check_error_state=True):
        """Run the middleware using a fake request."""
        if middleware is None:
            middleware = self.make_middleware()

        resolver = Mock()
        resolver.route = "/some/path"
        request = Mock()
        request.resolver_match = resolver

        middleware.process_view(request, None, None, None)

        if check_error_state:
            assert middleware.error is False

    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.error')
    def test_log_diagnostics_error_only_once(self, mock_log_error):
        """
        If the log_diagnostics function is broken, only log the error once.
        The method should still be called every time in case it is still doing
        useful work before the error, though.
        """
        middleware = self.make_middleware()

        bad_method = Mock(side_effect=lambda request: 1/0)
        middleware.log_diagnostics = bad_method

        self.run_middleware(middleware, check_error_state=False)
        self.run_middleware(middleware, check_error_state=False)
        assert middleware.error is True

        # Called twice
        assert len(bad_method.call_args_list) == 2

        # But only log once
        mock_log_error.assert_called_once_with(
            "Encountered error in DatadogDiagnosticMiddleware (suppressing further errors): "
            "ZeroDivisionError('division by zero')"
        )

    @ddt.data(
        # Feature disabled
        (False, False),
        (False, True),
        # Enabled, but nothing anomalous
        (True, False),
        # Enabled and anomaly detected
        (True, True),
    )
    @ddt.unpack
    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.warning')
    def test_anomalous_trace(self, enabled, cause_anomaly, mock_log_warning):
        with (
                patch.object(DETECT_ANOMALOUS_TRACE, 'is_enabled', return_value=enabled),
                patch.object(CLOSE_ANOMALOUS_SPANS, 'is_enabled', return_value=False),
                patch.object(LOG_ROOT_SPAN, 'is_enabled', return_value=False),
                # Need at least two levels of spans in order to fake
                # an anomaly. (Otherwise current_root_span returns None.)
                ddtrace.tracer.trace("local_root"),
                ddtrace.tracer.trace("intermediary_span"),
                ddtrace.tracer.trace("inner_span"),
        ):
            if cause_anomaly:
                ddtrace.tracer.current_root_span().finish()
            self.run_middleware()

        if enabled and cause_anomaly:
            mock_log_warning.assert_called_once()
            log_msg = mock_log_warning.call_args_list[0][0][0]  # first arg of first call

            assert re.fullmatch(
                r"Anomalous Datadog local root span: "
                r"trace_id=[0-9A-Fa-f]+; duration=[0-9]\.[0-9]{3}; worker_age=[0-9]\.[0-9]{3}; span ancestry:\n"
                r"name='local_root'.*duration=[0-9]+.*\n"
                r"name='intermediary_span'.*duration=None.*\n"
                r"name='inner_span'.*duration=None.*",
                log_msg
            )
        else:
            mock_log_warning.assert_not_called()

    @override_settings(DATADOG_DIAGNOSTICS_LOG_SPAN_DEPTH=2)
    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.warning')
    def test_anomalous_trace_truncation(self, mock_log_warning):
        """
        Test that truncation works, returning N most proximal spans.
        """
        with (
                patch.object(DETECT_ANOMALOUS_TRACE, 'is_enabled', return_value=True),
                patch.object(CLOSE_ANOMALOUS_SPANS, 'is_enabled', return_value=False),
                patch.object(LOG_ROOT_SPAN, 'is_enabled', return_value=False),
                # Need at least two levels of spans in order to fake
                # an anomaly. (Otherwise current_root_span returns None.)
                ddtrace.tracer.trace("local_root"),
                ddtrace.tracer.trace("intermediary_span"),
                ddtrace.tracer.trace("inner_span"),
        ):
            ddtrace.tracer.current_root_span().finish()  # cause anomaly
            self.run_middleware()

        mock_log_warning.assert_called_once()
        log_msg = mock_log_warning.call_args_list[0][0][0]  # first arg of first call

        assert re.fullmatch(
            r"Anomalous Datadog local root span: "
            r"trace_id=[0-9A-Fa-f]+; duration=[0-9]\.[0-9]{3}; worker_age=[0-9]\.[0-9]{3}; span ancestry:\n"
            r"\(ancestors truncated\)\n"  # difference here
            r"name='intermediary_span'.*duration=None.*\n"
            r"name='inner_span'.*duration=None.*",
            log_msg
        )

    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.info')
    def test_log_root_span(self, mock_log_info):
        with (
                patch.object(DETECT_ANOMALOUS_TRACE, 'is_enabled', return_value=False),
                patch.object(CLOSE_ANOMALOUS_SPANS, 'is_enabled', return_value=False),
                patch.object(LOG_ROOT_SPAN, 'is_enabled', return_value=True),
                # Need at least two levels of spans for interesting logging
                ddtrace.tracer.trace("local_root"),
                ddtrace.tracer.trace("inner_span"),
        ):
            self.run_middleware()

        mock_log_info.assert_called_once()
        log_msg = mock_log_info.call_args_list[0][0][0]  # first arg of first call
        assert re.fullmatch(
            r"Datadog span diagnostics: Route = /some/path; "
            r"local root span = name='local_root' .*; "
            r"current span = name='inner_span' .*",
            log_msg
        )

    def run_close_with(self, *, enabled, anomalous, ancestors=None):
        """
        Run a "close anomalous spans" scenario with supplied settings.

        ancestors is a list of span operation names, defaulting to
        something reasonable if not supplied.
        """
        with (
                patch.object(DETECT_ANOMALOUS_TRACE, 'is_enabled', return_value=False),
                patch.object(CLOSE_ANOMALOUS_SPANS, 'is_enabled', return_value=enabled),
                patch.object(LOG_ROOT_SPAN, 'is_enabled', return_value=False),
                ExitStack() as stack,
        ):
            if ancestors is None:
                ancestors = [
                    'django.request', 'django.view',
                    'celery.apply',
                    # ^ will need to close some of these
                    'django.request', 'django.view',
                ]
            for ancestor_name in ancestors:
                stack.enter_context(ddtrace.tracer.trace(ancestor_name))
            # make anomaly readily detectable
            if anomalous:
                ddtrace.tracer.current_root_span().finish()

            self.run_middleware()

    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.info')
    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.error')
    def test_close_disabled(self, mock_log_error, mock_log_info):
        """
        Confirm that nothing interesting happens when close-spans flag is disabled.
        """
        self.run_close_with(enabled=False, anomalous=True)

        mock_log_error.assert_not_called()
        mock_log_info.assert_not_called()

    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.info')
    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.error')
    def test_close_applied(self, mock_log_error, mock_log_info):
        """
        Confirm that anomalous spans are closed, at least for future requests.
        """
        self.run_close_with(enabled=True, anomalous=True)

        mock_log_error.assert_not_called()

        # Expect to close celery.apply and the one above it (but we've
        # already closed the root, above).
        assert len(mock_log_info.call_args_list) == 2
        assert [call[0][0].split(' id=')[0] for call in mock_log_info.call_args_list] == [
            "Closed span in anomalous trace: name=celery.apply",
            "Closed span in anomalous trace: name=django.view",
        ]

    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.info')
    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.error')
    def test_close_not_needed(self, mock_log_error, mock_log_info):
        """
        Confirm that no logging when anomalous trace not present.
        """
        self.run_close_with(enabled=True, anomalous=False)

        mock_log_error.assert_not_called()
        mock_log_info.assert_not_called()

    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.info')
    @patch('edx_arch_experiments.datadog_diagnostics.middleware.log.error')
    def test_close_missing_request(self, mock_log_error, mock_log_info):
        """
        Check that we look for the expected ancestor and only close above it.
        """
        self.run_close_with(enabled=True, anomalous=True, ancestors=[
            # Artificial scenario standing in for something unexpected.
            'django.view', 'celery.apply', 'django.view',
        ])

        mock_log_error.assert_called_once_with(
            "Did not find django.request span when walking anomalous trace to root. Not attempting a fix."
        )
        mock_log_info.assert_not_called()
