from django.conf import settings
from django.db import models

class Customer(models.Model):

    # FIX: SET_NULL (was CASCADE). Deleting a login account no longer tries to delete the
    # customer, whose vehicles are protected. The customer and the history stay.
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name='customer_profile',
        null=True,
        blank=True
    )
    name = models.CharField(max_length=100)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['-created_at', '-id']
        verbose_name_plural = 'Customers'
