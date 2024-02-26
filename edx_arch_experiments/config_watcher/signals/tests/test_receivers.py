"""
Test ConfigWatcher signal receivers (main code).
"""

import json
from contextlib import ExitStack
from unittest.mock import call, patch

import ddt
from django.test import TestCase, override_settings

from edx_arch_experiments.config_watcher.signals import receivers


@ddt.ddt
class TestConfigWatcherReceivers(TestCase):

    @ddt.unpack
    @ddt.data(
        (
            None, None, None,
        ),
        (
            'https://localhost', None, "test message",
        ),
        (
            'https://localhost', 'my-ida', "[my-ida] test message",
        ),
    )
    def test_send_to_slack(self, slack_url, service_name, expected_message):
        """Check that message prefixing is performed as expected."""
        # This can be made cleaner in Python 3.10
        with ExitStack() as stack:
            patches = [
                patch('urllib.request.Request'),
                patch('urllib.request.urlopen'),
                patch.object(receivers, 'CONFIG_WATCHER_SLACK_WEBHOOK_URL', slack_url),
                patch.object(receivers, 'CONFIG_WATCHER_SERVICE_NAME', service_name),
            ]
            (mock_req, _, _, _) = [stack.enter_context(cm) for cm in patches]
            receivers._send_to_slack("test message")

        if expected_message is None:
            mock_req.assert_not_called()
        else:
            mock_req.assert_called_once()
            (call_args, call_kwargs) = mock_req.call_args_list[0]
            assert json.loads(call_kwargs['data'])['text'] == expected_message
