# orders/views.py
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from events.models import Event
from .services import claim_portions_by_quantity, NotEnoughPortionsError


def claim_portions_view(request, event_id):
    if request.method != 'POST':
        return redirect('events:event_detail', event_id=event_id)

    event = get_object_or_404(Event, pk=event_id)
    claimant_name = request.POST.get('claimant_name', '').strip()

    if not claimant_name:
        messages.error(request, "Please enter your name.")
        return redirect('events:event_detail', event_id=event_id)

    # Collect quantity_<order_id> fields from the form
    requests = []
    for key, value in request.POST.items():
        if key.startswith('quantity_') and value:
            order_id = int(key.replace('quantity_', ''))
            quantity = int(value)
            if quantity > 0:
                requests.append((order_id, quantity))

    if not requests:
        messages.error(request, "Please select at least one portion.")
        return redirect('events:event_detail', event_id=event_id)

    try:
        claimed = claim_portions_by_quantity(requests, claimant_name)
        messages.success(request, f"Claimed {len(claimed)} portion(s)!")
    except NotEnoughPortionsError as e:
        messages.error(request, f"Sorry, not enough available in one of your selections. Nothing was claimed — please try again.")

    return redirect('events:event_detail', event_id=event_id)