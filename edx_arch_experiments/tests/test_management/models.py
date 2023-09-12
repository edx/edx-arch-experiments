from django.db import models

class TestPerson(models.Model):
    first_name = models.CharField(max_length=30)
    last_name = models.CharField(max_length=30)


class TestPersonContactInfo(models.Model):
    person = models.ForeignKey(TestPerson, on_delete=models.CASCADE)
    address = models.CharField(max_length=100)