from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class Role(models.TextChoices):
    ADMIN = "admin", "Admin"
    CUSTOMER = "customer", "Customer"
    MECHANIC = "mechanic", "Mechanic"


class AutoCareUserManager(UserManager):
    def create_superuser(self, username, email=None, password=None, **extra_fields):
        # FIX: manage.py createsuperuser used to give role "customer".
        extra_fields.setdefault("role", Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):

    ROLE_CHOICES = Role.choices  # kept, so old code that imports ROLE_CHOICES still works

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=15, unique=True, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    objects = AutoCareUserManager()

    def save(self, *args, **kwargs):
        # FIX: one format for ever. "Ali@X.com" and "ali@x.com" are the same person,
        # and an empty phone is stored as NULL (an empty string would clash with the unique rule).
        self.email = (self.email or "").strip().lower()
        self.phone = (self.phone or "").strip() or None
        super().save(*args, **kwargs)

    def __str__(self):
        return self.email
