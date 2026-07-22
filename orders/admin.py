# orders/admin.py
from django.contrib import admin
from .models import Order, Portion


class PortionInline(admin.TabularInline):
    model = Portion
    extra = 0
    readonly_fields = ("portion_number", "claimant_name", "claimed_at")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("menu_item", "event", "created_at")
    inlines = [PortionInline]


@admin.register(Portion)
class PortionAdmin(admin.ModelAdmin):
    list_display = ("order", "portion_number", "claimant_name", "claimed_at")
    list_filter = ("order__event",)