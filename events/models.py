from django.db import models
from organisations.models import Organisation
from vendors.models import Vendor

from config.utils import generate_public_id


class Event(models.Model):
    # 'locked' is a general-purpose "not currently accepting claims" state,
    # reusable both to prep an event before it opens and to pause an
    # already-open event temporarily - it isn't a one-way transition, unlike
    # 'closed' below. 'closed' specifically means the deadline has passed:
    # no more orders, and the event is being staged to send to the vendor.
    STATUS_CHOICES = [
        ("locked", "Locked"),
        ("open", "Open"),
        ("closed", "Closed"),
        ("submitted", "Submitted"),
    ]

    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="events")
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name="events")
    name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="locked")
    deadline = models.DateTimeField()
    public_id = models.CharField(max_length=10, unique=True, editable=False, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.organisation}) - {self.status}"

    def save(self, *args, **kwargs):
        if not self.public_id:
            public_id = generate_public_id()
            while Event.objects.filter(public_id=public_id).exists():
                public_id = generate_public_id()
            self.public_id = public_id
        super().save(*args, **kwargs)