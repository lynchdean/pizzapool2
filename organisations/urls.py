from django.urls import path

from events import views as event_views
from vendors import views as vendor_views

from . import views

app_name = 'organisations'

urlpatterns = [
    path('organisations/', views.my_organisations, name='my_organisations'),

    path('<slug:org_slug>/', views.organisation_detail, name='organisation_detail'),
    path('<slug:org_slug>/edit/', views.organisation_edit, name='organisation_edit'),

    path('<slug:org_slug>/vendors/new/', vendor_views.vendor_create, name='vendor_create'),
    path('<slug:org_slug>/vendors/<int:vendor_id>/', vendor_views.vendor_detail, name='vendor_detail'),
    path('<slug:org_slug>/vendors/<int:vendor_id>/edit/', vendor_views.vendor_edit, name='vendor_edit'),
    path('<slug:org_slug>/vendors/<int:vendor_id>/delete/', vendor_views.vendor_delete, name='vendor_delete'),
    path('<slug:org_slug>/vendors/<int:vendor_id>/menu-items/new/', vendor_views.menu_item_create, name='menu_item_create'),
    path('<slug:org_slug>/vendors/<int:vendor_id>/menu-items/<int:item_id>/edit/', vendor_views.menu_item_edit, name='menu_item_edit'),
    path('<slug:org_slug>/vendors/<int:vendor_id>/menu-items/<int:item_id>/delete/', vendor_views.menu_item_delete, name='menu_item_delete'),

    path('<slug:org_slug>/events/new/', event_views.event_create, name='event_create'),
    path('<slug:org_slug>/events/<int:event_id>/edit/', event_views.event_edit, name='event_edit'),
    path('<slug:org_slug>/events/<int:event_id>/delete/', event_views.event_delete, name='event_delete'),
]
