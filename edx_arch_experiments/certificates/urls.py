"""
Certificate retirement API URLs.
"""

from django.urls import path

from edx_arch_experiments.certificates.views import RetireCertificatesS3ForUserView, RetireCertificatesS3View

urlpatterns = [
    path('retire_certs_s3', RetireCertificatesS3View.as_view(), name='retire_certs_s3'),
    path('retire_certs_s3_for_user/', RetireCertificatesS3ForUserView.as_view(), name='retire_certs_s3_for_user'),
]
