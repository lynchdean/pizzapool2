# orders/views.py
from django.core.cache import cache
from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from events.models import Event
from vendors.models import MenuItem
from .forms import JoinOrderForm, StartOrderForm, UnclaimForm
from .models import Order
from .services import (
    claim_portions_by_quantity,
    start_order_and_claim,
    unclaim_portions,
    ClaimNotFoundError,
    NotEnoughPortionsError,
    EventNotOpenError,
)


def _flash_form_errors(request, form):
    for field_errors in form.errors.values():
        for error in field_errors:
            messages.error(request, error)


def _get_client_ip(request):
    # Behind the reverse proxy (Traefik/Coolify), REMOTE_ADDR is the proxy's
    # own internal IP for every request, which would collapse the rate limit
    # to one shared bucket for all users. The proxy appends the real client
    # IP as the last entry in X-Forwarded-For (any earlier entries could be
    # spoofed by the client itself, since the proxy doesn't strip them).
    # Falls back to REMOTE_ADDR for direct connections (e.g. local dev).
    forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded_for:
        return forwarded_for.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def _is_rate_limited(request, action, limit=10, period=60):
    ip = _get_client_ip(request)
    cache_key = f'ratelimit:{action}:{ip}'
    if cache.add(cache_key, 1, timeout=period):
        return False
    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=period)
        return False
    return count > limit


def join_order_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('event', 'event__organisation'), public_id=order_id
    )
    event = order.event

    if request.method != 'POST':
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event.public_id)

    if _is_rate_limited(request, 'join_order'):
        messages.error(request, "Too many attempts. Please wait a moment and try again.")
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event.public_id)

    max_quantity = order.portions.filter(claimant_name__isnull=True).count()
    form = JoinOrderForm(request.POST, max_quantity=max_quantity)

    if not form.is_valid():
        _flash_form_errors(request, form)
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event.public_id)

    try:
        claimed = claim_portions_by_quantity(
            event,
            [(order.id, form.cleaned_data['quantity'])],
            form.cleaned_data['claimant_name'],
            form.cleaned_data['claimant_phone'],
        )
        messages.success(request, f"Claimed {len(claimed)} portion(s)!")
    except EventNotOpenError:
        messages.error(request, "This event is no longer open for claims.")
    except NotEnoughPortionsError:
        messages.error(request, "Sorry, someone else just claimed those. Please try again.")

    return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event.public_id)


def unclaim_portion_view(request, order_id):
    order = get_object_or_404(
        Order.objects.select_related('event', 'event__organisation'), public_id=order_id
    )
    event = order.event

    if request.method != 'POST':
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event.public_id)

    if _is_rate_limited(request, 'unclaim_portion'):
        messages.error(request, "Too many attempts. Please wait a moment and try again.")
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event.public_id)

    form = UnclaimForm(request.POST)
    if not form.is_valid():
        _flash_form_errors(request, form)
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event.public_id)

    try:
        count = unclaim_portions(event, order.id, form.cleaned_data['claimant_phone'])
        messages.success(request, f"Cancelled {count} portion(s).")
    except EventNotOpenError:
        messages.error(request, "This event is no longer open, so claims can't be cancelled.")
    except ClaimNotFoundError:
        messages.error(request, "We couldn't find a claim matching that phone number on this order.")

    return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event.public_id)


def start_order_view(request, event_id):
    event = get_object_or_404(Event.objects.select_related('organisation'), public_id=event_id)

    if request.method != 'POST':
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event_id)

    if _is_rate_limited(request, 'start_order'):
        messages.error(request, "Too many attempts. Please wait a moment and try again.")
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event_id)

    menu_item_id = request.POST.get('menu_item_id', '')

    if not menu_item_id.isdigit():
        messages.error(request, "Invalid menu item selection.")
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event_id)

    menu_item = get_object_or_404(MenuItem, pk=menu_item_id, vendor=event.vendor, is_active=True)
    form = StartOrderForm(request.POST, max_quantity=menu_item.portions_per_unit)

    if not form.is_valid():
        _flash_form_errors(request, form)
        return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event_id)

    try:
        order, claimed = start_order_and_claim(
            event,
            menu_item,
            form.cleaned_data['quantity'],
            form.cleaned_data['claimant_name'],
            form.cleaned_data['claimant_phone'],
            form.cleaned_data['revolut_username'],
        )
        messages.success(
            request,
            f"Started a new order for {menu_item.name} and claimed {len(claimed)} portion(s)!",
        )
    except EventNotOpenError:
        messages.error(request, "This event is no longer open for new orders.")
    except NotEnoughPortionsError:
        messages.error(request, "You can't claim more portions than the order will contain.")

    return redirect('events:event_detail', org_slug=event.organisation.slug, event_id=event_id)
