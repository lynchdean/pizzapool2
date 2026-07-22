from django.db import models
from organisations.models import Organisation
from vendors.models import Vendor


class Event(models.Model):
    STATUS_CHOICES = [
        ("open", "Open"),
        ("locked", "Locked"),
        ("submitted", "Submitted"),
        ("completed", "Completed"),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="events")
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="events")
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="open")
    deadline = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.organisation}) - {self.status}"