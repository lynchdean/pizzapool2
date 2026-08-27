# events/services.py
from django.db import transaction
from orders.models import Portion
from .models import Event


class EventHasClaimedPortionsError(Exception):
    def __init__(self, event_id, claimed_count):
        self.event_id = event_id
        self.claimed_count = claimed_count
        super().__init__(f"Event {event_id} has {claimed_count} claimed portion(s); refusing to delete.")


def delete_event(event):
    with transaction.atomic():
        locked_event = Event.objects.select_for_update().get(pk=event.pk)
        claimed_count = Portion.objects.select_for_update().filter(
            order__event=locked_event, claimant_name__isnull=False
        ).count()

        if claimed_count:
            raise EventHasClaimedPortionsError(locked_event.pk, claimed_count)

        locked_event.delete()
