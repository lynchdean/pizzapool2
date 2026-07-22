from django.db import models

from django.conf import settings
from django.db import models


class Organisation(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class OrganisationMembership(models.Model):
    ROLE_CHOICES = [
        ("owner", "Owner"),
        ("organiser", "Organiser"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="memberships")
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="organiser")

    class Meta:
        unique_together = ("user", "organisation")

    def __str__(self):
        return f"{self.user} @ {self.organisation} ({self.role})"