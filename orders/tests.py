from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from organisations.models import Organisation
from vendors.models import Vendor, MenuItem
from .models import Order, Portion
from .services import (
    claim_portions_by_quantity,
    create_order,
    NotEnoughPortionsError,
    EventNotOpenError,
)


class ClaimPortionsByQuantityTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.menu_item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation,
            vendor=self.vendor,
            name="Friday Lunch",
            deadline=timezone.now(),
        )
        self.order = Order.objects.create(event=self.event, menu_item=self.menu_item)

    def test_claim_succeeds_when_event_open(self):
        claimed = claim_portions_by_quantity(self.event, [(self.order.id, 2)], "Alice")

        self.assertEqual(len(claimed), 2)
        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name="Alice").count(), 2
        )

    def test_claim_raises_event_not_open_error_for_locked_submitted_completed(self):
        for status in ("locked", "submitted", "completed"):
            with self.subTest(status=status):
                self.event.status = status
                self.event.save()

                with self.assertRaises(EventNotOpenError):
                    claim_portions_by_quantity(self.event, [(self.order.id, 1)], "Bob")

                self.assertEqual(
                    Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(),
                    0,
                )

    def test_claim_raises_not_enough_portions_when_order_belongs_to_different_event(self):
        other_event = Event.objects.create(
            organisation=self.organisation,
            vendor=self.vendor,
            name="Other Event",
            deadline=timezone.now(),
        )

        with self.assertRaises(NotEnoughPortionsError):
            claim_portions_by_quantity(other_event, [(self.order.id, 1)], "Eve")

        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 0
        )


class CreateOrderTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.menu_item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation,
            vendor=self.vendor,
            name="Friday Lunch",
            deadline=timezone.now(),
        )

    def test_create_order_succeeds_when_event_open(self):
        order = create_order(self.event, self.menu_item)

        self.assertEqual(
            Portion.objects.filter(order=order).count(), self.menu_item.portions_per_unit
        )

    def test_create_order_raises_event_not_open_error_for_locked_submitted_completed(self):
        for status in ("locked", "submitted", "completed"):
            with self.subTest(status=status):
                self.event.status = status
                self.event.save()

                with self.assertRaises(EventNotOpenError):
                    create_order(self.event, self.menu_item)

                self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_order_clean_raises_validation_error_when_event_not_open(self):
        self.event.status = "locked"
        self.event.save()

        order = Order(event=self.event, menu_item=self.menu_item)

        with self.assertRaises(ValidationError):
            order.full_clean()

    def test_order_clean_does_not_block_editing_an_existing_order(self):
        order = create_order(self.event, self.menu_item)
        self.event.status = "locked"
        self.event.save()

        order.full_clean()


class ClaimPortionsViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.menu_item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation,
            vendor=self.vendor,
            name="Friday Lunch",
            status="locked",
            deadline=timezone.now(),
        )
        self.order = Order.objects.create(event=self.event, menu_item=self.menu_item)

    def test_view_shows_error_and_claims_nothing_when_event_not_open(self):
        response = self.client.post(
            reverse("orders:claim_portions", args=[self.event.id]),
            {"claimant_name": "Alice", f"quantity_{self.order.id}": "2"},
            follow=True,
        )

        self.assertContains(response, "This event is no longer open for claims")
        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 0
        )

    def test_event_detail_hides_claim_form_when_event_not_open(self):
        response = self.client.get(reverse("events:event_detail", args=[self.event.id]))

        self.assertNotContains(response, "<form")
        self.assertContains(response, "This event is no longer open for claims")


class StartOrderViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.other_vendor = Vendor.objects.create(organisation=self.organisation, name="Other Vendor")
        self.menu_item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation,
            vendor=self.vendor,
            name="Friday Lunch",
            deadline=timezone.now(),
        )
        self.url = reverse("orders:start_order", args=[self.event.id])

    def test_get_redirects_without_creating_order(self):
        response = self.client.get(self.url)

        self.assertRedirects(response, reverse("events:event_detail", args=[self.event.id]))
        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_post_creates_order_for_active_menu_item(self):
        response = self.client.post(self.url, {"menu_item_id": self.menu_item.id}, follow=True)

        self.assertTrue(Order.objects.filter(event=self.event, menu_item=self.menu_item).exists())
        self.assertContains(response, "Started a new order for Margherita")

    def test_post_rejects_inactive_menu_item(self):
        self.menu_item.is_active = False
        self.menu_item.save()

        response = self.client.post(self.url, {"menu_item_id": self.menu_item.id})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_post_rejects_menu_item_from_different_vendor(self):
        other_item = MenuItem.objects.create(
            vendor=self.other_vendor, name="Not This Event's Item", portions_per_unit=4, price="10.00"
        )

        response = self.client.post(self.url, {"menu_item_id": other_item.id})

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_post_shows_error_and_creates_nothing_when_event_not_open(self):
        self.event.status = "locked"
        self.event.save()

        response = self.client.post(self.url, {"menu_item_id": self.menu_item.id}, follow=True)

        self.assertContains(response, "This event is no longer open for new orders.")
        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_anonymous_user_can_start_order(self):
        # Deliberate: starting an order is public, same as claiming portions —
        # do not add a login requirement here without revisiting that decision.
        # No force_login() call in this test — the client is anonymous.
        response = self.client.post(self.url, {"menu_item_id": self.menu_item.id})

        self.assertTrue(Order.objects.filter(event=self.event, menu_item=self.menu_item).exists())
        self.assertNotEqual(response.status_code, 403)
