from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify

RESERVED_SLUGS = {"admin", "accounts", "organisations", "orders", "static"}


class Organisation(models.Model):
    name = models.CharField(max_length=255, unique=True)
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        if slugify(self.name) in RESERVED_SLUGS:
            raise ValidationError({"name": "This organisation name is reserved and can't be used."})

    def save(self, *args, **kwargs):
        base_slug = slugify(self.name)
        slug = base_slug
        n = 2
        qs = Organisation.objects.exclude(pk=self.pk)
        while qs.filter(slug=slug).exists():
            slug = f"{base_slug}-{n}"
            n += 1
        self.slug = slug
        super().save(*args, **kwargs)


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