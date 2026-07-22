# orders/services.py
from django.db import transaction
from django.utils import timezone
from .models import Order, Portion


class PortionAlreadyClaimedError(Exception):
    pass


def create_order(event, menu_item):
    with transaction.atomic():
        order = Order.objects.create(event=event, menu_item=menu_item)
        portions = [
            Portion(order=order, portion_number=n)
            for n in range(1, menu_item.portions_per_unit + 1)
        ]
        Portion.objects.bulk_create(portions)
    return order


def claim_portion(portion_id, claimant_name):
    with transaction.atomic():
        portion = Portion.objects.select_for_update().get(pk=portion_id)
        if portion.claimant_name is not None:
            raise PortionAlreadyClaimedError(f"Portion {portion.portion_number} is already claimed")
        portion.claimant_name = claimant_name
        portion.claimed_at = timezone.now()
        portion.save()
    return portion