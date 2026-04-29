"""
Certificate retirement API URLs.
"""

from django.urls import path

from edx_arch_experiments.certificates.views import RetireCertificatesS3View

urlpatterns = [
    path('retire_certs_s3', RetireCertificatesS3View.as_view(), name='retire_certs_s3'),
]
