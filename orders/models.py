# orders/models.py
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone
from events.models import Event
from vendors.models import MenuItem
from phonenumber_field.modelfields import PhoneNumberField

from config.utils import generate_public_id


class Order(models.Model):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="orders")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT, related_name="orders")
    public_id = models.CharField(max_length=10, unique=True, editable=False, blank=True)
    # Nullable at the DB level since orders created before this field existed
    # have none - required at the form level for every new order instead
    # (see orders/forms.py:StartOrderForm).
    revolut_username = models.CharField(max_length=16, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    # Set once, at creation, by orders/services.py:start_order_and_claim - the
    # name shown as "<name>'s order" in event_detail.html. Deliberately its
    # own persisted field rather than derived from whichever Portion currently
    # has the earliest claimed_at: that derivation let anyone unclaim the
    # starter's portions, claim their own, and rename the order to themselves.
    started_by_name = models.CharField(max_length=255, blank=True)
    # Set once, at creation, alongside started_by_name - lets a joiner who
    # can't pay via Revolut contact the starter directly to arrange payment
    # some other way. Same "persist at creation, don't derive from live
    # claim data" reasoning as started_by_name.
    started_by_phone = PhoneNumberField(blank=True, null=True)

    def __str__(self):
        return f"{self.menu_item} for {self.event}"

    def clean(self):
        super().clean()
        if self._state.adding and self.event_id:
            # Deadline is checked alongside status for the same reason as
            # orders/services.py:_ensure_event_open - there's no background
            # job flipping status the instant a deadline passes.
            if self.event.status != "open" or self.event.deadline < timezone.now():
                raise ValidationError("Cannot create an order for an event that is not open.")

    def save(self, *args, **kwargs):
        # Backstop alongside StartOrderForm.clean_revolut_username - normalize
        # here too so nothing that sets this field directly (admin, shell,
        # future code) can save a mixed-case value and break its revolut.me
        # link.
        if self.revolut_username:
            self.revolut_username = self.revolut_username.lower()
        if not self.public_id:
            public_id = generate_public_id()
            while Order.objects.filter(public_id=public_id).exists():
                public_id = generate_public_id()
            self.public_id = public_id
        is_new = self._state.adding
        with transaction.atomic():
            super().save(*args, **kwargs)
            if is_new:
                self._generate_portions()

    def _generate_portions(self):
        from .models import Portion  # avoid circular import issues if split across files
        portions = [
            Portion(order=self, portion_number=n)
            for n in range(1, self.menu_item.portions_per_unit + 1)
        ]
        Portion.objects.bulk_create(portions)


class Portion(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="portions")
    portion_number = models.PositiveIntegerField()
    claimant_name = models.CharField(max_length=255, blank=True, null=True)
    claimant_phone = PhoneNumberField(blank=True, null=True)
    claimed_at = models.DateTimeField(blank=True, null=True)
    # Set once, at creation, by orders/services.py:start_order_and_claim for
    # the portions the starter claims for themselves - excluded from
    # unclaim_portions so the reservation an order was started with can't be
    # freed up and reclaimed by someone else out from under it. Stays True
    # forever once set, regardless of what happens to the claim afterward.
    is_starter_claim = models.BooleanField(default=False)

    class Meta:
        unique_together = ("order", "portion_number")
        ordering = ["portion_number"]

    def __str__(self):
        status = self.claimant_name or "unclaimed"
        return f"Portion {self.portion_number} of {self.order} ({status})"