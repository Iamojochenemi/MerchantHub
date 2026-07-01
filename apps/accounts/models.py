from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model for MerchantHub.
    Extends Django default user.
    """

    email = models.EmailField(unique=True)

    phone_number = models.CharField(max_length=20, null=True, blank=True)

    is_merchant = models.BooleanField(default=True)

    def __str__(self):
        return self.username