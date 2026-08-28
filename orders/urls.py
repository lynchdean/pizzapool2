from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('<order_id>/join/', views.join_order_view, name='join_order'),
    path('<order_id>/unclaim/', views.unclaim_portion_view, name='unclaim_portion'),
    path('events/<event_id>/start/', views.start_order_view, name='start_order'),
]