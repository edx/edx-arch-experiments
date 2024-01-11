"""
Test codejail service views.
"""

import json
import textwrap
from os import path

import ddt
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from edx_arch_experiments.codejail_service import views


@override_settings(
    ROOT_URLCONF='edx_arch_experiments.codejail_service.urls',
    MIDDLEWARE=[
        'django.contrib.sessions.middleware.SessionMiddleware',
    ],
)
@ddt.ddt
class TestExecService(TestCase):
    """Test the v0 code exec view."""

    def setUp(self):
        super().setUp()
        user_model = get_user_model()
        self.admin_user = user_model.objects.create_user('cms_worker', is_staff=True)
        self.other_user = user_model.objects.create_user('student', is_staff=False)
        self.standard_params = {'code': 'retval = 3 + 4', 'globals_dict': {}}

    def _test_codejail_api(self, *, user=None, skip_auth=False, params=None, files=None, exp_status, exp_body):
        """
        Call the view and make assertions.

        Args:
            user: User to authenticate as when calling view, defaulting to an is_staff user
            skip_auth: If true, do not send authentication headers (incompatible with `user` argument)
            params: Payload of codejail parameters, defaulting to a simple arithmetic check
            files: Files to include in the API call, as dict of filenames to file objects
            exp_status: Assert that the response HTTP status code is this value
            exp_body: Assert that the response body JSON is this value
        """
        assert not (user and skip_auth)

        client = APIClient()
        user = user or self.admin_user
        if not skip_auth:
            client.force_authenticate(user)

        params = self.standard_params if params is None else params
        payload = json.dumps(params)
        req_body = {'payload': payload, **(files or {})}

        resp = client.post(reverse('code_exec_v0'), req_body, format='multipart')

        assert resp.status_code == exp_status
        assert json.loads(resp.content) == exp_body

    def test_success(self):
        """Regular successful call."""
        self._test_codejail_api(
            exp_status=200, exp_body={'globals_dict': {'retval': 7}},
        )

    @override_settings(CODEJAIL_SERVICE_ENABLED=False)
    def test_feature_disabled(self):
        """Service can be disabled."""
        self._test_codejail_api(
            exp_status=500, exp_body={'error': "Codejail service not enabled"},
        )

    @override_settings(ENABLE_CODEJAIL_REST_SERVICE=True)
    def test_misconfigured_as_relay(self):
        """Don't accept codejail requests if we're going to send them elsewhere."""
        self._test_codejail_api(
            exp_status=500, exp_body={'error': "Codejail service is misconfigured. (Refusing to act as relay.)"},
        )

    def test_unauthenticated(self):
        """Anonymous requests are rejected."""
        self._test_codejail_api(
            skip_auth=True,
            exp_status=403, exp_body={'detail': "Authentication credentials were not provided."},
        )

    def test_unprivileged(self):
        """Anonymous requests are rejected."""
        self._test_codejail_api(
            user=self.other_user,
            exp_status=403, exp_body={'detail': "You do not have permission to perform this action."},
        )

    def test_unsafely(self):
        """unsafely=true is rejected"""
        self._test_codejail_api(
            params=dict(**self.standard_params, unsafely=True),
            exp_status=400, exp_body={'error': "Refusing codejail execution with unsafely=true"},
        )

    @ddt.unpack
    @ddt.data(
        ({'globals_dict': {}}, 'code'),
        ({'code': 'retval = 3 + 4'}, 'globals_dict'),
        ({}, 'code'),
    )
    def test_missing_params(self, params, missing):
        """Two code and globals_dict params are required."""
        self._test_codejail_api(
            params=params,
            exp_status=400, exp_body={
                'error': f"Payload JSON did not match schema: '{missing}' is a required property",
            },
        )

    def test_extra_files(self):
        """Check that we can include a course library."""
        # "Course library" containing `course_library.triangular_number`.
        #
        # It's tempting to use zipfile to write to an io.BytesIO so
        # that the test library is in plaintext. Django's request
        # factory will indeed see that as a file to use in a multipart
        # upload, but it will see it as an empty bytestring. (read()
        # returns empty bytestring, while getvalue() returns the
        # desired data). So instead we just have a small zip file on
        # disk here.
        library_path = path.join(path.dirname(__file__), 'test_course_library.zip')

        with open(library_path, 'rb') as lib_zip:
            self._test_codejail_api(
                params={
                    'code': textwrap.dedent("""
                        from course_library import triangular_number

                        result = triangular_number(6)
                    """),
                    'globals_dict': {},
                    'python_path': ['python_lib.zip'],
                },
                files={'python_lib.zip': lib_zip},
                exp_status=200, exp_body={'globals_dict': {'result': 21}},
            )

    def test_exception(self):
        """Report exceptions from jailed code."""
        self._test_codejail_api(
            params={'code': '1/0', 'globals_dict': {}},
            exp_status=200, exp_body={'emsg': 'ZeroDivisionError: division by zero'},
        )
