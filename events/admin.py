from django.contrib import admin
from .models import Event


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "organisation", "vendor", "status", "deadline")
    list_filter = ("status", "organisation")