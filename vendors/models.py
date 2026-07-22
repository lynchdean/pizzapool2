from django.db import models
from organisations.models import Organisation


class Vendor(models.Model):
    organisation = models.ForeignKey(Organisation, on_delete=models.CASCADE, related_name="vendors")
    name = models.CharField(max_length=255)
    contact_info = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("organisation", "name")

    def __str__(self):
        return f"{self.name} ({self.organisation})"


class MenuItem(models.Model):
    vendor = models.ForeignKey(Vendor, on_delete=models.CASCADE, related_name="menu_items")
    name = models.CharField(max_length=255)
    portions_per_unit = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("vendor", "name")

    def __str__(self):
        return f"{self.name} ({self.vendor})"