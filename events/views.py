from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render

from orders.models import Order, Portion
from organisations.models import Organisation
from organisations.permissions import organisation_member_required

from .forms import EventForm
from .models import Event
from .services import EventHasClaimedPortionsError, delete_event


def _get_org_event(organisation_id, event_id):
    return get_object_or_404(Event, pk=event_id, organisation_id=organisation_id)


# events/views.py
def event_detail(request, event_id):
    event = get_object_or_404(Event.objects.select_related('vendor'), pk=event_id)

    order_qs = Order.objects.filter(event=event).annotate(
        available_count=Count('portions', filter=Q(portions__claimant_name__isnull=True))
    ).order_by('created_at')

    menu_items = (
        event.vendor.menu_items
        .filter(Q(is_active=True) | Q(orders__event=event))
        .distinct()
        .prefetch_related(Prefetch('orders', queryset=order_qs, to_attr='event_orders'))
        .order_by('name')
    )
    for item in menu_items:
        for order in item.event_orders:
            order.available_range = range(1, order.available_count + 1)

    return render(request, 'events/event_detail.html', {
        'event': event,
        'menu_items': menu_items,
    })


@organisation_member_required
def event_create(request, organisation_id):
    organisation = get_object_or_404(Organisation, pk=organisation_id)

    if request.method == 'POST':
        form = EventForm(request.POST, organisation=organisation)
        if form.is_valid():
            event = form.save()
            messages.success(request, f"Event '{event.name}' created.")
            return redirect('organisations:organisation_detail', organisation_id=organisation.id)
    else:
        form = EventForm(organisation=organisation)

    return render(request, 'events/event_form.html', {
        'organisation': organisation,
        'form': form,
    })


@organisation_member_required
def event_edit(request, organisation_id, event_id):
    event = _get_org_event(organisation_id, event_id)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event, organisation=event.organisation)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated.")
            return redirect('organisations:organisation_detail', organisation_id=organisation_id)
    else:
        form = EventForm(instance=event, organisation=event.organisation)

    return render(request, 'events/event_form.html', {
        'organisation': event.organisation,
        'form': form,
        'event': event,
    })


@organisation_member_required
def event_delete(request, organisation_id, event_id):
    event = _get_org_event(organisation_id, event_id)
    claimed_count = Portion.objects.filter(order__event=event, claimant_name__isnull=False).count()

    if request.method == 'POST':
        try:
            name = event.name
            delete_event(event)
            messages.success(request, f"Event '{name}' deleted.")
            return redirect('organisations:organisation_detail', organisation_id=organisation_id)
        except EventHasClaimedPortionsError as e:
            claimed_count = e.claimed_count
            messages.error(request, f"Can't delete — {claimed_count} portion(s) have already been claimed.")

    return render(request, 'events/event_confirm_delete.html', {
        'event': event,
        'organisation_id': organisation_id,
        'claimed_count': claimed_count,
    })
