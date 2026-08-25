from django.db.models import Count, Q
from django.shortcuts import render, get_object_or_404
from .models import Event


# events/views.py
def event_detail(request, event_id):
    event = get_object_or_404(Event, pk=event_id)
    orders = event.orders.select_related('menu_item').annotate(
        available_count=Count('portions', filter=Q(portions__claimant_name__isnull=True))
    )

    for order in orders:
        order.available_range = range(1, order.available_count + 1)

    return render(request, 'events/event_detail.html', {
        'event': event,
        'orders': orders,
    })
