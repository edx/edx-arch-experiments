"""
Private API endpoint to delete retired learners' S3 certificate files and mark
the corresponding GeneratedCertificate records as deleted.

This view is intentionally kept in edx-arch-experiments (not upstreamed to
openedx/edx-platform) because it is specific to edx's retirement pipeline
infrastructure (S3 bucket layout, retired username pattern, AWS Secrets Manager
secret structure).

Endpoint: POST /api/certificates/v1/retire_certs_s3
"""

import logging
from urllib.parse import urlparse

import backoff
import boto3
from botocore.exceptions import ClientError
from lms.djangoapps.certificates.data import CertificateStatuses  # pylint: disable=import-error
from lms.djangoapps.certificates.models import GeneratedCertificate  # pylint: disable=import-error
from openedx.core.djangoapps.user_api.accounts.permissions import CanRetireUser  # pylint: disable=import-error
from rest_framework import permissions, status
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

log = logging.getLogger(__name__)

MAX_S3_ATTEMPTS = 5


class S3Client:
    """Thin wrapper around boto3 S3 client with exponential backoff."""

    def __init__(self):
        self.client = boto3.client('s3')

    @backoff.on_exception(backoff.expo, ClientError, max_tries=MAX_S3_ATTEMPTS)
    def delete_object(self, bucket, key):
        return self.client.delete_object(Bucket=bucket, Key=key)

    def delete_objects_by_prefix(self, bucket, prefix):
        paginator = self.client.get_paginator('list_objects_v2')
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
            for obj in page.get('Contents', []):
                self.delete_object(bucket, obj['Key'])


def _fetch_certs_to_delete():
    """
    Returns a queryset of GeneratedCertificate records belonging to retired
    users that still have a downloadable PDF certificate URL.

    Mirrors the SQL query in the legacy retired_user_cert_remover.py:
        WHERE au.username LIKE 'retired__user_%'
          AND gc.download_url LIKE '%https://%'
          AND gc.status = 'downloadable'
    """
    return GeneratedCertificate.objects.filter(
        user__username__startswith='retired_user_',
        download_url__icontains='https://',
        status=CertificateStatuses.downloadable,
    ).select_related('user').order_by('user_id', 'course_id')


def _s3_keys_from_cert(cert):
    """
    Derives S3 bucket name, verify prefix, and download key from a certificate.

    Returns (bucket, verify_prefix, download_key) or raises ValueError if the
    download_url cannot be parsed.
    """
    parsed = urlparse(cert.download_url)
    parts = parsed.path.lstrip('/').split('/', 1)
    if not parts or not parts[0]:
        raise ValueError(f'Cannot derive S3 bucket from download_url: {cert.download_url}')
    bucket = parts[0]
    verify_prefix = f'cert/{cert.verify_uuid}/'
    download_key = f'downloads/{cert.download_uuid}/Certificate.pdf'
    return bucket, verify_prefix, download_key


class RetireCertificatesS3View(APIView):
    """
    POST /api/certificates/v1/retire_certs_s3

    Finds all GeneratedCertificate records for retired users that still have a
    downloadable PDF URL, deletes the corresponding S3 objects, then marks the
    DB record as deleted.

    The S3 delete always happens before the DB update (per certificate). If S3
    fails the DB is left unchanged, so the certificate stays in the query and
    will be retried on the next invocation. S3 delete is idempotent for
    already-deleted objects, making retries safe.

    Query parameters:
        dry_run (bool, default false): when true, logs actions but makes no
            changes to S3 or the database.

    Auth: requires a JWT/OAuth token for a user with the
    ``accounts.can_retire_user`` permission (same permission used by all other
    retirement endpoints).

    Responses:
        200  All certificates processed successfully.
             Body: {"processed": <int>, "failed": []}
        207  Partial success — some certificates failed S3 deletion.
             Body: {"processed": <int>, "failed": [<cert_id>, ...]}
        500  Unexpected error before any processing began.
    """

    permission_classes = (permissions.IsAuthenticated, CanRetireUser)
    parser_classes = (JSONParser,)

    def post(self, request):
        """
        Delete S3 certificate files for retired learners and mark the
        corresponding GeneratedCertificate records as deleted in the database.
        """
        dry_run = request.query_params.get('dry_run', 'false').lower() == 'true'
        s3 = S3Client()

        try:
            certs = list(_fetch_certs_to_delete())
        except Exception as exc:  # pylint: disable=broad-except
            log.exception('retire_certs_s3: failed to query certificates: %s', exc)
            return Response(
                {'error': 'Failed to query certificates from database.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        log.info('retire_certs_s3: found %d certificate(s) to process (dry_run=%s)', len(certs), dry_run)

        processed = 0
        failed_ids = []

        for cert in certs:
            try:
                bucket, verify_prefix, download_key = _s3_keys_from_cert(cert)
            except ValueError as exc:
                log.error(
                    'retire_certs_s3: skipping cert %s (user %s) — bad download_url: %s',
                    cert.id, cert.user_id, exc,
                )
                failed_ids.append(cert.id)
                continue

            if dry_run:
                log.info(
                    '[dry_run] Would delete s3://%s/%s*, s3://%s/%s  |  cert_id=%s user_id=%s',
                    bucket, verify_prefix, bucket, download_key, cert.id, cert.user_id,
                )
                processed += 1
                continue

            try:
                # Delete S3 objects first. Only update the DB on success.
                s3.delete_objects_by_prefix(bucket, verify_prefix)
                s3.delete_object(bucket, download_key)

                cert.status = CertificateStatuses.deleted
                cert.download_url = ''
                cert.download_uuid = ''
                cert.save(update_fields=['status', 'download_url', 'download_uuid'])

                log.info(
                    'retire_certs_s3: cert %s (user %s) deleted from S3 and marked deleted in DB',
                    cert.id, cert.user_id,
                )
                processed += 1

            except ClientError as exc:
                log.error(
                    'retire_certs_s3: S3 error for cert %s (user %s): %s',
                    cert.id, cert.user_id, exc,
                )
                failed_ids.append(cert.id)
            except Exception as exc:  # pylint: disable=broad-except
                log.exception(
                    'retire_certs_s3: unexpected error for cert %s (user %s): %s',
                    cert.id, cert.user_id, exc,
                )
                failed_ids.append(cert.id)

        response_data = {'processed': processed, 'failed': failed_ids}

        if failed_ids:
            log.warning(
                'retire_certs_s3: completed with %d failure(s): cert_ids=%s',
                len(failed_ids), failed_ids,
            )
            return Response(response_data, status=status.HTTP_207_MULTI_STATUS)

        return Response(response_data, status=status.HTTP_200_OK)
