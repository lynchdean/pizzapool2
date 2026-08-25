from django.urls import path
from . import views

app_name = 'events'

urlpatterns = [
    path('<int:event_id>/', views.event_detail, name='event_detail'),
]