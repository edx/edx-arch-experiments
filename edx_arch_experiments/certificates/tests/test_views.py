"""
Unit tests for edx_arch_experiments.certificates.views.

All LMS-internal models and permissions are mocked at the module level so
these tests run standalone without an LMS Django environment.
"""

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock, Mock, patch

import ddt
import pytest
from botocore.exceptions import ClientError
from django.test import RequestFactory, TestCase
from rest_framework import status

# ---------------------------------------------------------------------------
# Stub out LMS modules that views.py imports at module load time.
# These must be installed before importing the views module.
# ---------------------------------------------------------------------------

def _make_module(name):
    mod = ModuleType(name)
    sys.modules[name] = mod
    return mod


_certs_data = _make_module('lms.djangoapps.certificates.data')
_certs_data.CertificateStatuses = MagicMock(downloadable='downloadable', deleted='deleted')

_certs_models = _make_module('lms.djangoapps.certificates.models')
_certs_models.GeneratedCertificate = MagicMock()

_user_api = _make_module('openedx.core.djangoapps.user_api')
_user_api_accounts = _make_module('openedx.core.djangoapps.user_api.accounts')
_user_api_perms = _make_module('openedx.core.djangoapps.user_api.accounts.permissions')
_user_api_perms.CanRetireUser = MagicMock()

# Ensure parent packages exist in sys.modules
for pkg in ('lms', 'lms.djangoapps', 'lms.djangoapps.certificates',
            'openedx', 'openedx.core', 'openedx.core.djangoapps'):
    if pkg not in sys.modules:
        sys.modules[pkg] = ModuleType(pkg)

# Now import the module under test
from edx_arch_experiments.certificates import views  # noqa: E402  pylint: disable=wrong-import-position

# Patch target strings — centralised so a rename only needs changing here.
_PATCH_FETCH_USER = 'edx_arch_experiments.certificates.views._fetch_certs_to_delete_for_user'
_PATCH_FETCH_ALL  = 'edx_arch_experiments.certificates.views._fetch_certs_to_delete'
_PATCH_S3         = 'edx_arch_experiments.certificates.views.S3Client'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cert(cert_id, user_id, download_url, verify_uuid='abc', download_uuid='def', course_id='course-v1:edX+Test+2026'):
    """Return a MagicMock mimicking a GeneratedCertificate instance."""
    cert = MagicMock()
    cert.id = cert_id
    cert.user_id = user_id
    cert.download_url = download_url
    cert.verify_uuid = verify_uuid
    cert.download_uuid = download_uuid
    cert.course_id = course_id
    cert.status = 'downloadable'
    return cert


_VALID_URL = 'https://s3.amazonaws.com/verify.edx.org/cert-123.pdf'
_VALID_URL2 = 'https://s3.amazonaws.com/verify.edx.org/cert-456.pdf'


# ---------------------------------------------------------------------------
# Tests for _s3_keys_from_cert
# ---------------------------------------------------------------------------

@ddt.ddt
class TestS3KeysFromCert(TestCase):
    """Tests for the _s3_keys_from_cert helper."""

    def test_valid_path_style_url(self):
        cert = _make_cert(1, 10, _VALID_URL, verify_uuid='v1', download_uuid='d1')
        bucket, verify_prefix, download_key = views._s3_keys_from_cert(cert)
        assert bucket == 'verify.edx.org'
        assert verify_prefix == 'cert/v1/'
        assert download_key == 'downloads/d1/Certificate.pdf'

    @ddt.data(
        ('https://cdn.example.com/bucket/key', 'Unexpected S3 host'),
        (f'https://{views._EXPECTED_S3_HOST}/', 'Cannot derive S3 bucket'),
    )
    @ddt.unpack
    def test_bad_url_raises_value_error(self, url, expected_msg):
        cert = _make_cert(1, 10, url)
        with pytest.raises(ValueError, match=expected_msg):
            views._s3_keys_from_cert(cert)


# ---------------------------------------------------------------------------
# Tests for _retire_single_cert
# ---------------------------------------------------------------------------

@ddt.ddt
class TestRetireSingleCert(TestCase):
    """Tests for the shared _retire_single_cert helper."""

    def _make_s3(self, side_effect=None):
        s3 = MagicMock()
        s3.delete_objects_by_prefix = MagicMock(side_effect=side_effect)
        s3.delete_object = MagicMock()
        return s3

    def test_success(self):
        cert = _make_cert(1, 10, _VALID_URL, verify_uuid='v1', download_uuid='d1')
        s3 = self._make_s3()
        result = views._retire_single_cert(s3, cert, 'test')
        assert result is True
        s3.delete_objects_by_prefix.assert_called_once_with('verify.edx.org', 'cert/v1/')
        s3.delete_object.assert_called_once_with('verify.edx.org', 'downloads/d1/Certificate.pdf')
        cert.save.assert_called_once()

    def test_db_fields_updated_on_success(self):
        cert = _make_cert(1, 10, _VALID_URL, verify_uuid='v1', download_uuid='d1')
        s3 = self._make_s3()
        views._retire_single_cert(s3, cert, 'test')
        assert cert.status == views.CertificateStatuses.deleted
        assert cert.download_url == ''
        assert cert.download_uuid == ''

    def _client_error(self):
        return ClientError({'Error': {'Code': 'AccessDenied', 'Message': 'denied'}}, 'DeleteObjects')

    @ddt.data(
        # (url, s3_side_effect)  — all cases must return False and skip save
        ('https://cdn.example.com/bad', None),           # bad URL: ValueError before S3 call
        (_VALID_URL, 'client_error'),                    # S3 ClientError
        (_VALID_URL, RuntimeError('boom')),              # unexpected exception
    )
    @ddt.unpack
    def test_failure_returns_false_and_skips_save(self, url, s3_side_effect):
        if s3_side_effect == 'client_error':
            s3_side_effect = self._client_error()
        cert = _make_cert(1, 10, url, verify_uuid='v1', download_uuid='d1')
        s3 = self._make_s3(side_effect=s3_side_effect)
        result = views._retire_single_cert(s3, cert, 'test')
        assert result is False
        cert.save.assert_not_called()


# ---------------------------------------------------------------------------
# Base class for view tests — handles auth bypass
# ---------------------------------------------------------------------------

class _BaseViewTestCase(TestCase):
    """
    Bypasses DRF permission checking so view logic can be tested in isolation.

    DRF's ``Request`` wrapper re-derives ``request.user`` via its own
    authentication pipeline, so setting ``request.user = Mock(…)`` on a plain
    Django request has no effect.  Setting ``permission_classes = []`` directly
    on each view class before the test is the most reliable bypass — DRF's
    ``get_permissions()`` simply returns an empty list and ``check_permissions``
    performs no checks.
    """

    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        # Strip permissions from both view classes for the duration of each test.
        from edx_arch_experiments.certificates.views import (
            RetireCertificatesS3ForUserView,
            RetireCertificatesS3View,
        )
        self._saved = {
            RetireCertificatesS3ForUserView: RetireCertificatesS3ForUserView.permission_classes,
            RetireCertificatesS3View: RetireCertificatesS3View.permission_classes,
        }
        RetireCertificatesS3ForUserView.permission_classes = []
        RetireCertificatesS3View.permission_classes = []

    def tearDown(self):
        from edx_arch_experiments.certificates.views import (
            RetireCertificatesS3ForUserView,
            RetireCertificatesS3View,
        )
        for cls, original in self._saved.items():
            cls.permission_classes = original
        super().tearDown()


# ---------------------------------------------------------------------------
# Tests for RetireCertificatesS3ForUserView
# ---------------------------------------------------------------------------

@ddt.ddt
class TestRetireCertificatesS3ForUserView(_BaseViewTestCase):
    """Tests for POST /api/certificates/v1/retire_certs_s3_for_user."""

    def _post(self, data=None):
        from edx_arch_experiments.certificates.views import RetireCertificatesS3ForUserView
        request = self.factory.post(
            '/api/certificates/v1/retire_certs_s3_for_user',
            data=json.dumps(data or {}),
            content_type='application/json',
        )
        return RetireCertificatesS3ForUserView.as_view()(request)

    @ddt.data(
        {},                          # username key absent entirely
        {'username': '   '},         # username present but blank after strip
    )
    def test_bad_username_returns_400(self, body):
        response = self._post(body)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'username' in response.data['error']

    @patch(_PATCH_FETCH_USER, return_value=[])
    def test_no_certs_returns_200(self, _mock_fetch):
        response = self._post({'username': 'retired__user_abc'})
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'username': 'retired__user_abc', 'processed': 0, 'failed': []}

    @patch(_PATCH_S3)
    @patch(_PATCH_FETCH_USER)
    def test_all_certs_succeed_returns_200(self, mock_fetch, _MockS3):
        mock_fetch.return_value = [
            _make_cert(1, 10, _VALID_URL,  verify_uuid='v1', download_uuid='d1'),
            _make_cert(2, 10, _VALID_URL2, verify_uuid='v2', download_uuid='d2'),
        ]
        response = self._post({'username': 'retired__user_abc'})
        assert response.status_code == status.HTTP_200_OK
        assert response.data['processed'] == 2
        assert response.data['failed'] == []

    @patch(_PATCH_S3)
    @patch(_PATCH_FETCH_USER)
    def test_partial_failure_returns_207(self, mock_fetch, MockS3):
        mock_fetch.return_value = [
            _make_cert(1, 10, _VALID_URL,  verify_uuid='v1', download_uuid='d1'),
            _make_cert(2, 10, _VALID_URL2, verify_uuid='v2', download_uuid='d2'),
        ]
        MockS3.return_value.delete_objects_by_prefix.side_effect = [
            None,
            ClientError({'Error': {'Code': 'AccessDenied', 'Message': 'denied'}}, 'DeleteObjects'),
        ]
        response = self._post({'username': 'retired__user_abc'})
        assert response.status_code == status.HTTP_207_MULTI_STATUS
        assert response.data['processed'] == 1
        assert response.data['failed'] == [2]

    @patch(_PATCH_FETCH_USER, return_value=[_make_cert(1, 10, 'https://cdn.example.com/bad')])
    def test_all_certs_fail_returns_207(self, _mock_fetch):
        response = self._post({'username': 'retired__user_abc'})
        assert response.status_code == status.HTTP_207_MULTI_STATUS
        assert response.data['processed'] == 0
        assert response.data['failed'] == [1]

    @patch(_PATCH_FETCH_USER, side_effect=RuntimeError('db error'))
    def test_db_query_error_returns_500(self, _mock_fetch):
        response = self._post({'username': 'retired__user_abc'})
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch(_PATCH_FETCH_USER, return_value=[])
    def test_username_is_stripped(self, mock_fetch):
        self._post({'username': '  retired__user_abc  '})
        mock_fetch.assert_called_once_with('retired__user_abc')


# ---------------------------------------------------------------------------
# Tests for RetireCertificatesS3View (batch)
# ---------------------------------------------------------------------------

class TestRetireCertificatesS3View(_BaseViewTestCase):
    """Tests for POST /api/certificates/v1/retire_certs_s3."""

    def _post(self, query_string=''):
        from edx_arch_experiments.certificates.views import RetireCertificatesS3View
        request = self.factory.post(
            f'/api/certificates/v1/retire_certs_s3{query_string}',
            content_type='application/json',
        )
        return RetireCertificatesS3View.as_view()(request)

    @patch(_PATCH_FETCH_ALL)
    def test_no_certs_returns_200(self, mock_fetch):
        mock_fetch.return_value.iterator.return_value = iter([])
        response = self._post()
        assert response.status_code == status.HTTP_200_OK
        assert response.data == {'processed': 0, 'failed': []}

    @patch(_PATCH_S3)
    @patch(_PATCH_FETCH_ALL)
    def test_all_certs_succeed_returns_200(self, mock_fetch, _MockS3):
        mock_fetch.return_value.iterator.return_value = iter([
            _make_cert(1, 10, _VALID_URL,  verify_uuid='v1', download_uuid='d1'),
            _make_cert(2, 20, _VALID_URL2, verify_uuid='v2', download_uuid='d2'),
        ])
        response = self._post()
        assert response.status_code == status.HTTP_200_OK
        assert response.data['processed'] == 2
        assert response.data['failed'] == []

    @patch(_PATCH_S3)
    @patch(_PATCH_FETCH_ALL)
    def test_partial_failure_returns_207(self, mock_fetch, MockS3):
        mock_fetch.return_value.iterator.return_value = iter([
            _make_cert(1, 10, _VALID_URL,  verify_uuid='v1', download_uuid='d1'),
            _make_cert(2, 20, _VALID_URL2, verify_uuid='v2', download_uuid='d2'),
        ])
        MockS3.return_value.delete_objects_by_prefix.side_effect = [
            None,
            ClientError({'Error': {'Code': 'AccessDenied', 'Message': 'denied'}}, 'DeleteObjects'),
        ]
        response = self._post()
        assert response.status_code == status.HTTP_207_MULTI_STATUS
        assert response.data['processed'] == 1
        assert response.data['failed'] == [2]

    @patch(_PATCH_S3)
    @patch(_PATCH_FETCH_ALL)
    def test_dry_run_makes_no_changes(self, mock_fetch, MockS3):
        cert = _make_cert(1, 10, _VALID_URL, verify_uuid='v1', download_uuid='d1')
        mock_fetch.return_value.iterator.return_value = iter([cert])
        response = self._post('?dry_run=true')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['processed'] == 1
        MockS3.return_value.delete_objects_by_prefix.assert_not_called()
        MockS3.return_value.delete_object.assert_not_called()
        cert.save.assert_not_called()

    @patch(_PATCH_FETCH_ALL, side_effect=RuntimeError('db error'))
    def test_db_query_error_returns_500(self, _mock_fetch):
        response = self._post()
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR

    @patch(_PATCH_S3)
    @patch(_PATCH_FETCH_ALL)
    def test_dry_run_false_by_default(self, mock_fetch, MockS3):
        """dry_run query param defaults to false — changes ARE made."""
        cert = _make_cert(1, 10, _VALID_URL, verify_uuid='v1', download_uuid='d1')
        mock_fetch.return_value.iterator.return_value = iter([cert])
        self._post()
        MockS3.return_value.delete_objects_by_prefix.assert_called_once()


# ---------------------------------------------------------------------------
# Tests for _fetch_certs_to_delete_for_user
# ---------------------------------------------------------------------------

class TestFetchCertsToDeleteForUser(TestCase):
    """Tests for the per-user queryset helper."""

    def test_calls_filter_with_correct_username(self):
        mock_qs = MagicMock()
        views.GeneratedCertificate.objects.filter.return_value.select_related.return_value.order_by.return_value = mock_qs
        result = views._fetch_certs_to_delete_for_user('retired__user_abc')
        views.GeneratedCertificate.objects.filter.assert_called_once_with(
            user__username='retired__user_abc',
            download_url__icontains='https://',
            status=views.CertificateStatuses.downloadable,
        )
        assert result == mock_qs
