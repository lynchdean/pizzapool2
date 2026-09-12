from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from organisations.models import Organisation, OrganisationMembership
from vendors.models import Vendor, MenuItem
from .models import Order, Portion
from .services import (
    claim_portions_by_quantity,
    create_order,
    delete_order,
    unclaim_portions,
    ClaimNotFoundError,
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
            status='open',
        )
        self.order = Order.objects.create(event=self.event, menu_item=self.menu_item)

    def test_claim_succeeds_when_event_open(self):
        claimed = claim_portions_by_quantity(self.event, [(self.order.id, 2)], "Alice")

        self.assertEqual(len(claimed), 2)
        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name="Alice").count(), 2
        )

    def test_claim_persists_claimant_phone(self):
        claim_portions_by_quantity(self.event, [(self.order.id, 1)], "Alice", "+353871234567")

        portion = Portion.objects.get(order=self.order, claimant_name="Alice")
        self.assertEqual(str(portion.claimant_phone), "+353871234567")

    def test_claim_raises_event_not_open_error_for_locked_closed_submitted(self):
        for status in ("locked", "closed", "submitted"):
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
            status='open',
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
            status='open',
        )

    def test_create_order_succeeds_when_event_open(self):
        order = create_order(self.event, self.menu_item)

        self.assertEqual(
            Portion.objects.filter(order=order).count(), self.menu_item.portions_per_unit
        )

    def test_create_order_raises_event_not_open_error_for_locked_closed_submitted(self):
        for status in ("locked", "closed", "submitted"):
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


class JoinOrderViewTests(TestCase):
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
            status='open',
        )
        self.order = Order.objects.create(event=self.event, menu_item=self.menu_item)
        self.url = reverse("orders:join_order", args=[self.order.public_id])
        self.valid_data = {
            "claimant_name": "Bob",
            "claimant_phone": "0871234567",
            "quantity": 2,
        }

    def test_get_redirects_without_claiming(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response, reverse("events:event_detail", args=[self.organisation.slug, self.event.public_id])
        )
        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 0
        )

    def test_post_claims_portions_with_name_and_phone(self):
        response = self.client.post(self.url, self.valid_data, follow=True)

        claimed = Portion.objects.filter(order=self.order, claimant_name="Bob")
        self.assertEqual(claimed.count(), 2)
        self.assertTrue(claimed.exclude(claimant_phone="").exists())
        self.assertContains(response, "Claimed 2 portion(s) of Margherita!")

    def test_looking_up_by_raw_integer_pk_returns_404(self):
        url = reverse("orders:join_order", args=[str(self.order.pk)])

        response = self.client.post(url, self.valid_data)

        self.assertEqual(response.status_code, 404)

    def test_missing_phone_shows_error_and_claims_nothing(self):
        data = {**self.valid_data}
        del data["claimant_phone"]

        self.client.post(self.url, data, follow=True)

        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 0
        )

    def test_non_numeric_quantity_shows_error_and_claims_nothing(self):
        data = {**self.valid_data, "quantity": "abc"}

        self.client.post(self.url, data, follow=True)

        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 0
        )

    def test_quantity_exceeding_available_shows_error_and_claims_nothing(self):
        data = {**self.valid_data, "quantity": self.menu_item.portions_per_unit + 1}

        self.client.post(self.url, data, follow=True)

        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 0
        )

    def test_shows_error_and_claims_nothing_when_event_not_open(self):
        self.event.status = "locked"
        self.event.save()

        response = self.client.post(self.url, self.valid_data, follow=True)

        self.assertContains(response, "&#x27;Friday Lunch&#x27; is no longer open for claims")
        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 0
        )

    def test_exceeding_rate_limit_blocks_further_attempts(self):
        data = {**self.valid_data}
        del data["claimant_phone"]  # invalid but cheap: no DB writes per request

        for _ in range(10):
            response = self.client.post(self.url, data, follow=True)
            self.assertNotContains(response, "Too many attempts")

        response = self.client.post(self.url, data, follow=True)

        self.assertContains(response, "Too many attempts")

    def test_rate_limit_is_tracked_per_ip_not_globally(self):
        data = {**self.valid_data}
        del data["claimant_phone"]

        for _ in range(11):
            self.client.post(self.url, data, REMOTE_ADDR="1.1.1.1")

        # A fresh Client, not just a different REMOTE_ADDR on the same one,
        # so this doesn't pick up unconsumed flash messages left over from
        # the redirect-only (no follow=True) requests above.
        other_visitor = Client()
        response = other_visitor.post(self.url, data, REMOTE_ADDR="2.2.2.2", follow=True)

        self.assertNotContains(response, "Too many attempts")


class UnclaimPortionViewTests(TestCase):
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
            status='open',
        )
        self.order = Order.objects.create(event=self.event, menu_item=self.menu_item)
        claim_portions_by_quantity(self.event, [(self.order.id, 2)], "Bob", "+353871234567")
        self.url = reverse("orders:unclaim_portion", args=[self.order.public_id])

    def test_get_redirects_without_unclaiming(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response, reverse("events:event_detail", args=[self.organisation.slug, self.event.public_id])
        )
        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 2
        )

    def test_post_with_correct_phone_releases_the_claim(self):
        response = self.client.post(
            self.url, {"claimant_phone": "+353871234567"}, follow=True
        )

        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 0
        )
        self.assertContains(response, "Cancelled 2 portion(s) of Margherita.")

    def test_post_with_nonmatching_reference_changes_nothing(self):
        # claimant_phone here is a reference key (see UnclaimForm/unclaim_portions),
        # not a user-typed identity check - this simulates a stale page / race
        # (the claim was already cancelled) rather than someone "getting the
        # phone number wrong".
        response = self.client.post(
            self.url, {"claimant_phone": "+353879999999"}, follow=True
        )

        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 2
        )
        self.assertContains(response, "may have already been cancelled")

    def test_unclaiming_one_claimant_does_not_affect_another(self):
        claim_portions_by_quantity(self.event, [(self.order.id, 1)], "Carol", "+353871111111")

        self.client.post(self.url, {"claimant_phone": "+353871234567"})

        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name="Carol").count(), 1
        )

    def test_blocked_and_unchanged_when_event_not_open(self):
        self.event.status = "locked"
        self.event.save()

        response = self.client.post(
            self.url, {"claimant_phone": "+353871234567"}, follow=True
        )

        self.assertContains(response, "no longer open, so claims")
        self.assertEqual(
            Portion.objects.filter(order=self.order, claimant_name__isnull=False).count(), 2
        )

    def test_exceeding_rate_limit_blocks_further_attempts(self):
        data = {"claimant_phone": "+353879999999"}  # wrong number: fast, no side effects

        for _ in range(10):
            response = self.client.post(self.url, data, follow=True)
            self.assertNotContains(response, "Too many attempts")

        response = self.client.post(self.url, data, follow=True)

        self.assertContains(response, "Too many attempts")

    def test_rate_limit_is_tracked_per_ip_not_globally(self):
        data = {"claimant_phone": "+353879999999"}

        for _ in range(11):
            self.client.post(self.url, data, REMOTE_ADDR="1.1.1.1")

        other_visitor = Client()
        response = other_visitor.post(self.url, data, REMOTE_ADDR="2.2.2.2", follow=True)

        self.assertNotContains(response, "Too many attempts")


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
            status='open',
        )
        self.url = reverse("orders:start_order", args=[self.event.public_id])
        self.valid_data = {
            "menu_item_id": self.menu_item.id,
            "claimant_name": "Alice",
            "claimant_phone": "0871234567",
            "quantity": 2,
            "revolut_username": "alice92",
        }

    def test_get_redirects_without_creating_order(self):
        response = self.client.get(self.url)

        self.assertRedirects(
            response, reverse("events:event_detail", args=[self.organisation.slug, self.event.public_id])
        )
        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_post_creates_order_and_claims_portions_for_starter(self):
        response = self.client.post(self.url, self.valid_data, follow=True)

        order = Order.objects.get(event=self.event, menu_item=self.menu_item)
        self.assertEqual(Portion.objects.filter(order=order, claimant_name="Alice").count(), 2)
        self.assertContains(response, "Started a new order for Margherita")

    def test_post_rejects_inactive_menu_item(self):
        self.menu_item.is_active = False
        self.menu_item.save()

        response = self.client.post(self.url, self.valid_data)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_post_rejects_menu_item_from_different_vendor(self):
        other_item = MenuItem.objects.create(
            vendor=self.other_vendor, name="Not This Event's Item", portions_per_unit=4, price="10.00"
        )
        data = {**self.valid_data, "menu_item_id": other_item.id}

        response = self.client.post(self.url, data)

        self.assertEqual(response.status_code, 404)
        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_post_shows_error_and_creates_nothing_when_event_not_open(self):
        self.event.status = "locked"
        self.event.save()

        response = self.client.post(self.url, self.valid_data, follow=True)

        self.assertContains(response, "&#x27;Friday Lunch&#x27; is no longer open for new orders.")
        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_exceeding_rate_limit_blocks_further_attempts(self):
        data = {**self.valid_data, "menu_item_id": "not-a-number"}  # invalid but cheap

        for _ in range(10):
            response = self.client.post(self.url, data, follow=True)
            self.assertNotContains(response, "Too many attempts")

        response = self.client.post(self.url, data, follow=True)

        self.assertContains(response, "Too many attempts")

    def test_rate_limit_is_tracked_per_ip_not_globally(self):
        data = {**self.valid_data, "menu_item_id": "not-a-number"}

        for _ in range(11):
            self.client.post(self.url, data, REMOTE_ADDR="1.1.1.1")

        # A fresh Client, not just a different REMOTE_ADDR on the same one,
        # so this doesn't pick up unconsumed flash messages left over from
        # the redirect-only (no follow=True) requests above.
        other_visitor = Client()
        response = other_visitor.post(self.url, data, REMOTE_ADDR="2.2.2.2", follow=True)

        self.assertNotContains(response, "Too many attempts")

    def test_post_rejects_quantity_exceeding_portions_per_unit(self):
        data = {**self.valid_data, "quantity": self.menu_item.portions_per_unit + 1}

        self.client.post(self.url, data, follow=True)

        self.assertFalse(Order.objects.filter(event=self.event).exists())
        self.assertFalse(
            Portion.objects.filter(order__event=self.event, claimant_name__isnull=False).exists()
        )

    def test_post_requires_phone(self):
        data = {**self.valid_data}
        del data["claimant_phone"]

        self.client.post(self.url, data, follow=True)

        self.assertFalse(Order.objects.filter(event=self.event).exists())

    def test_anonymous_user_can_start_order(self):
        # Deliberate: starting an order is public, same as claiming portions.
        # Do not add a login requirement here without revisiting that decision.
        # No force_login() call in this test: the client is anonymous.
        response = self.client.post(self.url, self.valid_data)

        order = Order.objects.filter(event=self.event, menu_item=self.menu_item).first()
        self.assertIsNotNone(order)
        self.assertTrue(Portion.objects.filter(order=order, claimant_name="Alice").exists())
        self.assertNotEqual(response.status_code, 403)


class DeleteOrderServiceTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.menu_item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now(),
            status='open',
        )

    def test_delete_order_removes_order_when_no_claims(self):
        order = Order.objects.create(event=self.event, menu_item=self.menu_item)

        delete_order(order)

        self.assertFalse(Order.objects.filter(pk=order.pk).exists())

    def test_delete_order_removes_order_even_with_claimed_portions(self):
        # No claimed-portions guard here, unlike delete_event: every order
        # has at least the starter's own claim by the time it exists, so
        # blocking on that would make deletion impossible in practice.
        order = Order.objects.create(event=self.event, menu_item=self.menu_item)
        for portion in list(order.portions.all())[:2]:
            portion.claimant_name = "Alice"
            portion.save()

        delete_order(order)

        self.assertFalse(Order.objects.filter(pk=order.pk).exists())


class DeleteOrderViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.owner = User.objects.create_user(username="owner", password="pw")
        OrganisationMembership.objects.create(
            user=self.owner, organisation=self.organisation, role="owner"
        )
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.menu_item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now(),
            status='open',
        )
        self.order = Order.objects.create(event=self.event, menu_item=self.menu_item)
        self.url = reverse("orders:delete_order", args=[self.order.public_id])

    def test_get_redirects_without_deleting(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.url)

        self.assertRedirects(
            response, reverse("events:event_detail", args=[self.organisation.slug, self.event.public_id])
        )
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_post_deletes_order_with_no_claimed_portions_as_owner(self):
        self.client.force_login(self.owner)

        response = self.client.post(self.url, follow=True)

        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())
        self.assertContains(response, "&#x27;Margherita&#x27; order deleted.")

    def test_post_deletes_order_as_superuser(self):
        superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        self.client.force_login(superuser)

        self.client.post(self.url)

        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())

    def test_post_deletes_order_even_with_claimed_portions(self):
        self.client.force_login(self.owner)
        portion = self.order.portions.first()
        portion.claimant_name = "Alice"
        portion.save()

        response = self.client.post(self.url, follow=True)

        self.assertFalse(Order.objects.filter(pk=self.order.pk).exists())
        self.assertContains(response, "&#x27;Margherita&#x27; order deleted.")

    def test_post_forbidden_for_organiser(self):
        organiser = User.objects.create_user(username="organiser", password="pw")
        OrganisationMembership.objects.create(
            user=organiser, organisation=self.organisation, role="organiser"
        )
        self.client.force_login(organiser)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_post_forbidden_for_anonymous(self):
        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())

    def test_post_forbidden_for_non_member(self):
        other_user = User.objects.create_user(username="other", password="pw")
        self.client.force_login(other_user)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 403)
        self.assertTrue(Order.objects.filter(pk=self.order.pk).exists())
