# orders/models.py
from django.db import models
from events.models import Event
from vendors.models import MenuItem


class Order(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="orders")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="orders")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.menu_item} for {self.event}"


class Portion(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="portions")
    portion_number = models.PositiveIntegerField()
    claimant_name = models.CharField(max_length=255, blank=True, null=True)
    claimed_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        unique_together = ("order", "portion_number")
        ordering = ["portion_number"]

    def __str__(self):
        status = self.claimant_name or "unclaimed"
        return f"Portion {self.portion_number} of {self.order} ({status})"