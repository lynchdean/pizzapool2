from django.urls import path
from . import views

app_name = 'orders'

urlpatterns = [
    path('events/<int:event_id>/claim/', views.claim_portions_view, name='claim_portions'),
]