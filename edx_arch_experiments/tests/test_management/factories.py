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

    address = '123 4th st, Fiveville, AZ, 67890'
    command = 'manufacture_data'