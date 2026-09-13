# orders/services.py
from django.db import transaction
from django.utils import timezone
from events.models import Event
from .models import Portion, Order


def _ensure_event_open(locked_event):
    """
    Raises EventNotOpenError unless the event is genuinely open right now.
    Checks the deadline as well as status: this app has no background job to
    flip status='open' to 'closed' the instant a deadline passes (status gets
    updated opportunistically elsewhere, e.g. on page load), so relying on
    status alone would let a claim through in the window between the
    deadline passing and something next writing the new status.
    """
    if locked_event.status != "open" or locked_event.deadline < timezone.now():
        raise EventNotOpenError(locked_event.pk, locked_event.status)


def create_order(event, menu_item):
    with transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.pk)
        _ensure_event_open(locked_event)
        return Order.objects.create(event=locked_event, menu_item=menu_item)


class NotEnoughPortionsError(Exception):
    def __init__(self, order_id, requested, available):
        self.order_id = order_id
        self.requested = requested
        self.available = available
        super().__init__(f"Order {order_id}: requested {requested}, only {available} available")


class EventNotOpenError(Exception):
    def __init__(self, event_id, status):
        self.event_id = event_id
        self.status = status
        super().__init__(f"Event {event_id} is not open (status={status})")


class ClaimNotFoundError(Exception):
    def __init__(self, order_id):
        self.order_id = order_id
        super().__init__(f"No claimed portions found on order {order_id} for that phone number")


def claim_portions_by_quantity(event, requests, claimant_name, claimant_phone=None):
    """
    event: the Event the given order_ids are expected to belong to. Re-fetched
        and locked inside the transaction so a status change racing with this
        submission (e.g. an organiser locking the event mid-request) is caught
        rather than silently ignored.
    requests: list of (order_id, quantity) tuples.
    All-or-nothing across the whole submission.
    Locks the event first, then orders in a consistent order (sorted by
    order_id), to avoid deadlocks with concurrent submissions.
    """
    sorted_requests = sorted(requests, key=lambda r: r[0])
    claimed_portions = []

    with transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.pk)
        _ensure_event_open(locked_event)

        for order_id, quantity in sorted_requests:
            if quantity <= 0:
                continue

            available = list(
                Portion.objects
                .select_for_update()
                .filter(
                    order_id=order_id,
                    order__event=locked_event,
                    claimant_name__isnull=True,
                )
                .order_by('portion_number')[:quantity]
            )

            if len(available) < quantity:
                raise NotEnoughPortionsError(order_id, quantity, len(available))

            claimed_portions.extend(available)

        now = timezone.now()
        for portion in claimed_portions:
            portion.claimant_name = claimant_name
            portion.claimant_phone = claimant_phone
            portion.claimed_at = now
            portion.save()

    return claimed_portions


def start_order_and_claim(event, menu_item, quantity, claimant_name, claimant_phone=None, revolut_username=None):
    """
    Atomically creates a new Order for menu_item within event and immediately
    claims `quantity` of its own freshly-generated portions for the starter.
    Order creation and the starter's own claim succeed or fail together: if
    the claim fails (event flips status mid-request, or quantity exceeds
    menu_item.portions_per_unit) the whole transaction rolls back and no
    orphaned zero-claim order is left behind.
    """
    with transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.pk)
        _ensure_event_open(locked_event)

        order = Order.objects.create(
            event=locked_event, menu_item=menu_item, revolut_username=revolut_username or None,
        )
        claimed = claim_portions_by_quantity(
            locked_event, [(order.id, quantity)], claimant_name, claimant_phone
        )

    return order, claimed


# Unlike delete_event, this has no claimed-portions guard: start_order_and_claim
# always claims at least one portion for the starter, so every order has a
# claim by design - blocking on that would make this feature unusable. The
# safety net here is the permission gate (owner/superuser only) plus the
# confirm() dialog in the template, not a data-integrity check.
def delete_order(order):
    order.delete()


def unclaim_portions(event, order_id, claimant_phone):
    """
    Releases every portion on order_id claimed under claimant_phone, freeing
    them up for someone else to claim. claimant_phone is a reference key
    here, not an identity check - the caller isn't proving they're that
    claimant, just telling us which claimant group on this order to release
    (the "Cancel claim" button passes it via a hidden, server-filled field,
    not something the visitor types in). Matches purely on phone number (per
    product decision): if multiple different names share one phone on the
    same order, this releases all of them together.
    """
    with transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.pk)
        _ensure_event_open(locked_event)

        portions = list(
            Portion.objects
            .select_for_update()
            .filter(order_id=order_id, order__event=locked_event, claimant_phone=claimant_phone)
        )
        if not portions:
            raise ClaimNotFoundError(order_id)

        for portion in portions:
            portion.claimant_name = None
            portion.claimant_phone = None
            portion.claimed_at = None
            portion.save()

    return len(portions)