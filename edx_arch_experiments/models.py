"""
Models for testing migrations.

We don't actually store any data in this Django app. The models here are purely
for pipeline and deployment testing purposes.
"""

from django.db import models


class Boms227(models.Model):
    """
    Model for testing migrations and rollbacks. See BOMS-227.

    .. no_pii: No data should actually be stored in this table.
    """

    dummy_field = models.CharField(max_length=50)
