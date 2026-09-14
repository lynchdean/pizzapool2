# orders/admin.py
from django.contrib import admin
from .models import Order, Portion


class PortionInline(admin.TabularInline):
    model = Portion
    extra = 0
    can_delete = False
    readonly_fields = ("portion_number", "claimant_name", "claimed_at", "is_starter_claim")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("menu_item", "event", "started_by_name", "public_id", "created_at")
    inlines = [PortionInline]


@admin.register(Portion)
class PortionAdmin(admin.ModelAdmin):
    list_display = ("order", "portion_number", "claimant_name", "claimed_at", "is_starter_claim")
    list_filter = ("order__event", "is_starter_claim")