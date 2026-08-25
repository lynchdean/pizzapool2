# orders/views.py
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from events.models import Event
from vendors.models import MenuItem
from .services import (
    claim_portions_by_quantity,
    create_order,
    NotEnoughPortionsError,
    EventNotOpenError,
)


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
        claimed = claim_portions_by_quantity(event, requests, claimant_name)
        messages.success(request, f"Claimed {len(claimed)} portion(s)!")
    except EventNotOpenError:
        messages.error(request, "This event is no longer open for claims.")
    except NotEnoughPortionsError:
        messages.error(request, "Sorry, not enough available in one of your selections. Nothing was claimed — please try again.")

    return redirect('events:event_detail', event_id=event_id)


def start_order_view(request, event_id):
    if request.method != 'POST':
        return redirect('events:event_detail', event_id=event_id)

    event = get_object_or_404(Event, pk=event_id)
    menu_item_id = request.POST.get('menu_item_id', '')

    if not menu_item_id.isdigit():
        messages.error(request, "Invalid menu item selection.")
        return redirect('events:event_detail', event_id=event_id)

    menu_item = get_object_or_404(MenuItem, pk=menu_item_id, vendor=event.vendor, is_active=True)

    try:
        create_order(event, menu_item)
        messages.success(request, f"Started a new order for {menu_item.name}.")
    except EventNotOpenError:
        messages.error(request, "This event is no longer open for new orders.")

    return redirect('events:event_detail', event_id=event_id)
