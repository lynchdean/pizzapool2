from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "organisation", "vendor", "status", "deadline", "public_id")
    list_filter = ("status", "organisation")