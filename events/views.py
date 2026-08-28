from decimal import ROUND_HALF_UP, Decimal

from django.contrib import messages
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render

from orders.models import Order, Portion
from organisations.models import Organisation
from organisations.permissions import organisation_member_required

from .forms import EventForm
from .models import Event
from .services import EventHasClaimedPortionsError, delete_event


def _get_org_event(org_slug, event_id):
    return get_object_or_404(Event, public_id=event_id, organisation__slug=org_slug)


# events/views.py
def event_detail(request, org_slug, event_id):
    event = get_object_or_404(
        Event.objects.select_related('vendor', 'organisation'),
        public_id=event_id, organisation__slug=org_slug,
    )

    portion_qs = Portion.objects.filter(claimant_name__isnull=False).order_by('claimed_at', 'id')

    orders = (
        Order.objects.filter(event=event)
        .select_related('menu_item')
        .annotate(available_count=Count('portions', filter=Q(portions__claimant_name__isnull=True)))
        .prefetch_related(Prefetch('portions', queryset=portion_qs, to_attr='claimed_portions'))
        .order_by('created_at')
    )
    for order in orders:
        order.available_range = range(1, order.available_count + 1)
        order.is_fully_claimed = order.available_count == 0

        claimants = {}
        for portion in order.claimed_portions:
            key = (portion.claimant_name, str(portion.claimant_phone))
            group = claimants.setdefault(key, {
                'name': portion.claimant_name,
                'phone': portion.claimant_phone,
                'quantity': 0,
            })
            group['quantity'] += 1
        order.claimants = list(claimants.values())
        order.started_by = order.claimants[0] if order.claimants else None

        if order.menu_item.portions_per_unit:
            order.price_per_portion = (
                order.menu_item.price / order.menu_item.portions_per_unit
            ).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        else:
            order.price_per_portion = None

    active_menu_items = list(event.vendor.menu_items.filter(is_active=True).order_by('name'))

    return render(request, 'events/event_detail.html', {
        'event': event,
        'orders': orders,
        'active_menu_items': active_menu_items,
    })


@organisation_member_required
def event_create(request, org_slug):
    organisation = get_object_or_404(Organisation, slug=org_slug)

    if request.method == 'POST':
        form = EventForm(request.POST, organisation=organisation)
        if form.is_valid():
            event = form.save()
            messages.success(request, f"Event '{event.name}' created.")
            return redirect('organisations:organisation_detail', org_slug=organisation.slug)
    else:
        form = EventForm(organisation=organisation)

    return render(request, 'events/event_form.html', {
        'organisation': organisation,
        'form': form,
    })


@organisation_member_required
def event_edit(request, org_slug, event_id):
    event = _get_org_event(org_slug, event_id)

    if request.method == 'POST':
        form = EventForm(request.POST, instance=event, organisation=event.organisation)
        if form.is_valid():
            form.save()
            messages.success(request, "Event updated.")
            return redirect('organisations:organisation_detail', org_slug=org_slug)
    else:
        form = EventForm(instance=event, organisation=event.organisation)

    return render(request, 'events/event_form.html', {
        'organisation': event.organisation,
        'form': form,
        'event': event,
    })


@organisation_member_required
def event_delete(request, org_slug, event_id):
    event = _get_org_event(org_slug, event_id)
    claimed_count = Portion.objects.filter(order__event=event, claimant_name__isnull=False).count()

    if request.method == 'POST':
        try:
            name = event.name
            delete_event(event)
            messages.success(request, f"Event '{name}' deleted.")
            return redirect('organisations:organisation_detail', org_slug=org_slug)
        except EventHasClaimedPortionsError as e:
            claimed_count = e.claimed_count
            messages.error(request, f"Can't delete — {claimed_count} portion(s) have already been claimed.")

    return render(request, 'events/event_confirm_delete.html', {
        'event': event,
        'org_slug': org_slug,
        'claimed_count': claimed_count,
    })
