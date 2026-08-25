# orders/services.py
from django.db import transaction
from django.utils import timezone
from .models import Portion, Order


def create_order(event, menu_item):
    return Order.objects.create(event=event, menu_item=menu_item)

class NotEnoughPortionsError(Exception):
    def __init__(self, order_id, requested, available):
        self.order_id = order_id
        self.requested = requested
        self.available = available
        super().__init__(f"Order {order_id}: requested {requested}, only {available} available")


def claim_portions_by_quantity(requests, claimant_name):
    """
    requests: list of (order_id, quantity) tuples.
    All-or-nothing across the whole submission.
    Locks orders in a consistent order (sorted by order_id) to avoid deadlocks.
    """
    sorted_requests = sorted(requests, key=lambda r: r[0])
    claimed_portions = []

    with transaction.atomic():
        for order_id, quantity in sorted_requests:
            if quantity <= 0:
                continue

            available = list(
                Portion.objects
                .select_for_update()
                .filter(order_id=order_id, claimant_name__isnull=True)
                .order_by('portion_number')[:quantity]
            )

            if len(available) < quantity:
                raise NotEnoughPortionsError(order_id, quantity, len(available))

            claimed_portions.extend(available)

        now = timezone.now()
        for portion in claimed_portions:
            portion.claimant_name = claimant_name
            portion.claimed_at = now
            portion.save()

    return claimed_portions