"""
Factories for models used in testing manufacture_data command
"""

import factory

from edx_arch_experiments.tests.test_management.models import TestPerson, TestPersonContactInfo


class TestPersonFactory(factory.django.DjangoModelFactory):
    """
    Test Factory for TestPerson
    """
    class Meta:
        model = TestPerson

    first_name = 'John'
    last_name = 'Doe'


class TestPersonContactInfoFactory(factory.django.DjangoModelFactory):
    """
    Test Factory for TestPersonContactInfo
    """
    class Meta:
        model = TestPersonContactInfo

    test_person = factory.SubFactory(TestPersonFactory)
    address = '123 4th st, Fiveville, AZ, 67890'
