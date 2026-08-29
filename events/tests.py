from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from orders.models import Order, Portion
from orders.services import claim_portions_by_quantity
from organisations.models import Organisation, OrganisationMembership
from vendors.models import MenuItem, Vendor

from .models import Event
from .services import EventHasClaimedPortionsError, delete_event


class EventCreateViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.other_organisation = Organisation.objects.create(name="Other Co")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.other_user = User.objects.create_user(username="other", password="pw")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.other_vendor = Vendor.objects.create(organisation=self.other_organisation, name="Other Vendor")
        self.url = reverse("organisations:event_create", args=[self.organisation.slug])

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)

        expected_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(response, expected_url)

    def test_non_member_gets_403(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_member_can_create_event(self):
        self.client.force_login(self.member)
        deadline = timezone.now() + timezone.timedelta(days=1)

        response = self.client.post(self.url, {
            "vendor": self.vendor.id,
            "name": "Friday Lunch",
            "status": "open",
            "deadline": deadline.strftime("%Y-%m-%d %H:%M:%S"),
        })

        event = Event.objects.get(name="Friday Lunch")
        self.assertEqual(event.organisation, self.organisation)
        self.assertRedirects(
            response, reverse("organisations:organisation_detail", args=[self.organisation.slug])
        )

    def test_deadline_field_renders_as_native_datetime_picker(self):
        self.client.force_login(self.member)

        response = self.client.get(self.url)

        self.assertContains(response, 'type="datetime-local"')

    def test_member_can_create_event_with_native_picker_format(self):
        self.client.force_login(self.member)
        deadline = timezone.now() + timezone.timedelta(days=1)

        response = self.client.post(self.url, {
            "vendor": self.vendor.id,
            "name": "Native Picker Lunch",
            "status": "open",
            "deadline": deadline.strftime("%Y-%m-%dT%H:%M"),
        })

        self.assertRedirects(
            response, reverse("organisations:organisation_detail", args=[self.organisation.slug])
        )
        self.assertTrue(Event.objects.filter(name="Native Picker Lunch").exists())

    def test_vendor_choices_restricted_to_organisations_own_vendors(self):
        self.client.force_login(self.member)
        deadline = timezone.now() + timezone.timedelta(days=1)

        response = self.client.post(self.url, {
            "vendor": self.other_vendor.id,
            "name": "Friday Lunch",
            "status": "open",
            "deadline": deadline.strftime("%Y-%m-%d %H:%M:%S"),
        })

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "vendor",
            "Select a valid choice. That choice is not one of the available choices.",
        )
        self.assertFalse(Event.objects.filter(name="Friday Lunch").exists())


class EventEditViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.other_organisation = Organisation.objects.create(name="Other Co")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.other_organisation, role="owner"
        )
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.other_vendor = Vendor.objects.create(organisation=self.organisation, name="Other Vendor")
        self.event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now() + timezone.timedelta(days=1),
        )
        self.item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.url = reverse("organisations:event_edit", args=[self.organisation.slug, self.event.public_id])
        self.client.force_login(self.member)

    def test_member_can_edit_event_fields(self):
        response = self.client.post(self.url, {
            "vendor": self.vendor.id,
            "name": "Friday Lunch (updated)",
            "status": "locked",
            "deadline": self.event.deadline.strftime("%Y-%m-%d %H:%M:%S"),
        })

        self.assertRedirects(
            response, reverse("events:event_detail", args=[self.organisation.slug, self.event.public_id])
        )
        self.event.refresh_from_db()
        self.assertEqual(self.event.name, "Friday Lunch (updated)")
        self.assertEqual(self.event.status, "locked")

    def test_cancel_link_points_to_event_detail(self):
        response = self.client.get(self.url)

        self.assertContains(
            response, reverse("events:event_detail", args=[self.organisation.slug, self.event.public_id])
        )

    def test_delete_link_shown_on_edit_page(self):
        response = self.client.get(self.url)

        self.assertContains(
            response, reverse("organisations:event_delete", args=[self.organisation.slug, self.event.public_id])
        )

    def test_vendor_field_ignored_when_event_has_orders(self):
        Order.objects.create(event=self.event, menu_item=self.item)

        self.client.post(self.url, {
            "vendor": self.other_vendor.id,
            "name": self.event.name,
            "status": "open",
            "deadline": self.event.deadline.strftime("%Y-%m-%d %H:%M:%S"),
        })

        self.event.refresh_from_db()
        self.assertEqual(self.event.vendor, self.vendor)

    def test_event_belonging_to_other_organisation_returns_404(self):
        url = reverse("organisations:event_edit", args=[self.other_organisation.slug, self.event.public_id])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)


class DeleteEventServiceTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now(),
        )

    def test_delete_event_removes_event_when_no_claims(self):
        Order.objects.create(event=self.event, menu_item=self.item)

        delete_event(self.event)

        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    def test_delete_event_raises_when_any_portion_claimed(self):
        order = Order.objects.create(event=self.event, menu_item=self.item)
        portion = order.portions.first()
        portion.claimant_name = "Alice"
        portion.save()

        with self.assertRaises(EventHasClaimedPortionsError):
            delete_event(self.event)

        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())

    def test_delete_event_raises_with_correct_claimed_count_across_multiple_orders(self):
        order1 = Order.objects.create(event=self.event, menu_item=self.item)
        item2 = MenuItem.objects.create(
            vendor=self.vendor, name="Pepperoni", portions_per_unit=4, price="12.00"
        )
        order2 = Order.objects.create(event=self.event, menu_item=item2)

        for portion in list(order1.portions.all())[:2]:
            portion.claimant_name = "Alice"
            portion.save()
        for portion in list(order2.portions.all())[:1]:
            portion.claimant_name = "Bob"
            portion.save()

        with self.assertRaises(EventHasClaimedPortionsError) as ctx:
            delete_event(self.event)

        self.assertEqual(ctx.exception.claimed_count, 3)


class EventDeleteViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now(),
        )
        self.url = reverse("organisations:event_delete", args=[self.organisation.slug, self.event.public_id])
        self.client.force_login(self.member)

    def test_get_shows_confirmation_with_zero_claimed_count(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Yes, delete this event")

    def test_post_deletes_event_with_no_claimed_portions(self):
        Order.objects.create(event=self.event, menu_item=self.item)

        response = self.client.post(self.url)

        self.assertRedirects(
            response, reverse("organisations:organisation_detail", args=[self.organisation.slug])
        )
        self.assertFalse(Event.objects.filter(pk=self.event.pk).exists())

    def test_get_blocks_deletion_when_portions_claimed(self):
        order = Order.objects.create(event=self.event, menu_item=self.item)
        portion = order.portions.first()
        portion.claimant_name = "Alice"
        portion.save()

        response = self.client.get(self.url)

        self.assertNotContains(response, "Yes, delete this event")

    def test_post_refuses_to_delete_when_portions_claimed(self):
        order = Order.objects.create(event=self.event, menu_item=self.item)
        portion = order.portions.first()
        portion.claimant_name = "Alice"
        portion.save()

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Event.objects.filter(pk=self.event.pk).exists())


class EventDetailViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now(),
        )
        self.url = reverse("events:event_detail", args=[self.organisation.slug, self.event.public_id])

    def test_wrong_org_slug_returns_404(self):
        other_org = Organisation.objects.create(name="Other Co")

        response = self.client.get(
            reverse("events:event_detail", args=[other_org.slug, self.event.public_id])
        )

        self.assertEqual(response.status_code, 404)

    def test_edit_link_hidden_for_anonymous_visitors(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, "Edit event")

    def test_edit_link_hidden_for_non_members(self):
        other_user = User.objects.create_user(username="other", password="pw")
        self.client.force_login(other_user)

        response = self.client.get(self.url)

        self.assertNotContains(response, "Edit event")

    def test_edit_link_shown_to_members(self):
        member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=member, organisation=self.organisation, role="organiser"
        )
        self.client.force_login(member)

        response = self.client.get(self.url)

        self.assertContains(response, "Edit event")
        self.assertContains(
            response, reverse("organisations:event_edit", args=[self.organisation.slug, self.event.public_id])
        )

    def test_edit_link_shown_to_superuser(self):
        superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        self.client.force_login(superuser)

        response = self.client.get(self.url)

        self.assertContains(response, "Edit event")

    def test_looking_up_by_raw_integer_pk_returns_404(self):
        url = reverse("events:event_detail", args=[self.organisation.slug, str(self.event.pk)])

        response = self.client.get(url)

        self.assertEqual(response.status_code, 404)

    def test_live_content_polls_via_htmx_when_event_open(self):
        response = self.client.get(self.url)

        self.assertContains(response, 'id="live-content"')
        self.assertContains(response, f'hx-get="{self.url}"')
        self.assertContains(response, 'hx-trigger="every 15s')
        self.assertContains(response, 'hx-select="#live-content"')
        self.assertContains(response, 'hx-target="#live-content"')

    def test_no_htmx_polling_when_event_not_open(self):
        self.event.status = "locked"
        self.event.save()

        response = self.client.get(self.url)

        self.assertNotContains(response, "hx-trigger")

    def test_order_details_still_visible_when_locked(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")
        self.event.status = "locked"
        self.event.save()

        response = self.client.get(self.url)

        self.assertContains(response, "Margherita")
        self.assertContains(response, "Alice")
        self.assertContains(response, "<td>1</td>", html=True)

    def test_join_and_start_forms_hidden_when_not_open(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        Order.objects.create(event=self.event, menu_item=item)
        self.event.status = "locked"
        self.event.save()

        response = self.client.get(self.url)

        self.assertNotContains(response, "Join (")
        self.assertNotContains(response, "Start a new order")

    def test_menu_item_with_no_orders_offers_start_section(self):
        MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )

        response = self.client.get(self.url)

        self.assertContains(response, "Margherita")
        self.assertContains(response, "Start a new order")
        self.assertContains(response, '<option value="" disabled selected>Choose a menu item</option>')
        self.assertNotContains(response, "Round 1")

    def test_menu_item_with_open_order_offers_join_and_the_start_section_stays(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")

        response = self.client.get(self.url)

        self.assertContains(response, "Claim a slice (3 left)")
        self.assertContains(response, "Start a new order")

    def test_start_section_dropdown_lists_only_active_menu_items(self):
        margherita = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        pepperoni = MenuItem.objects.create(
            vendor=self.vendor, name="Pepperoni", portions_per_unit=4, price="12.00"
        )
        MenuItem.objects.create(
            vendor=self.vendor, name="Discontinued Pizza", portions_per_unit=4, price="9.00",
            is_active=False,
        )

        response = self.client.get(self.url)

        self.assertContains(response, f'<option value="{margherita.id}">Margherita</option>')
        self.assertContains(response, f'<option value="{pepperoni.id}">Pepperoni</option>')
        self.assertNotContains(response, "Discontinued Pizza")

    def test_inactive_menu_item_with_existing_order_still_joinable_no_start_button(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00", is_active=False
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")

        response = self.client.get(self.url)

        self.assertContains(response, "Claim a slice (3 left)")
        self.assertNotContains(response, "Start another order")
        self.assertNotContains(response, "Start an order")

    def test_order_header_shows_earliest_claimant_as_starter(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")

        response = self.client.get(self.url)

        self.assertContains(response, "Alice's order")

    def test_order_header_shows_price_per_portion(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        Order.objects.create(event=self.event, menu_item=item)

        response = self.client.get(self.url)

        self.assertContains(response, "€2.50/portion")

    def test_price_per_portion_rounds_to_two_decimal_places(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Odd Pizza", portions_per_unit=3, price="10.00"
        )
        Order.objects.create(event=self.event, menu_item=item)

        response = self.client.get(self.url)

        self.assertContains(response, "€3.33/portion")

    def test_order_header_uses_organisations_currency_symbol(self):
        self.organisation.currency = "GBP"
        self.organisation.save()
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        Order.objects.create(event=self.event, menu_item=item)

        response = self.client.get(self.url)

        self.assertContains(response, "£2.50/portion")
        self.assertNotContains(response, "€2.50/portion")

    def test_order_shows_claimant_roster_with_name_and_phone(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "+353871234567")

        response = self.client.get(self.url)

        self.assertContains(response, "Alice")
        self.assertContains(response, "<td>1</td>", html=True)
        self.assertContains(response, "+353871234567")

    def test_cancel_control_shown_for_claimant_while_open(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "+353871234567")

        response = self.client.get(self.url)

        self.assertContains(
            response, reverse("orders:unclaim_portion", args=[order.public_id])
        )

    def test_cancel_form_prefills_the_correct_claimants_phone(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "+353871234567")
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Bob", "+353879999999")

        response = self.client.get(self.url)
        content = response.content.decode()

        self.assertIn('<input type="hidden" name="claimant_phone" value="+353871234567">', content)
        self.assertIn('<input type="hidden" name="claimant_phone" value="+353879999999">', content)

    def test_cancel_control_hidden_once_not_open(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "+353871234567")
        self.event.status = "locked"
        self.event.save()

        response = self.client.get(self.url)

        self.assertNotContains(
            response, reverse("orders:unclaim_portion", args=[order.public_id])
        )

    def test_repeat_claims_by_same_person_grouped_into_one_roster_line(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")

        response = self.client.get(self.url)

        self.assertContains(response, "<td>2</td>", html=True)

    def test_fully_claimed_order_shows_full_indicator_while_open(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=1, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")

        response = self.client.get(self.url)

        self.assertContains(response, "Full")
        self.assertNotContains(response, "Confirmed")
        self.assertNotContains(response, "Join (")

    def test_partially_claimed_order_shows_no_status_label_while_open(self):
        # The "Claim a slice (N left)" accordion button already shows the
        # remaining count, so no redundant fraction label is shown here.
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")

        response = self.client.get(self.url)

        self.assertNotContains(response, "1/4 claimed")
        self.assertNotContains(response, "will not proceed")

    def test_partially_claimed_order_still_shows_no_status_label_when_locked(self):
        # 'locked' isn't necessarily "closed": it may be used to prep an
        # event before it opens, so it shouldn't claim a partial order is
        # doomed the way 'submitted'/'completed' can.
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")
        self.event.status = "locked"
        self.event.save()

        response = self.client.get(self.url)

        self.assertNotContains(response, "1/4 claimed")
        self.assertNotContains(response, "will not proceed")

    def test_partially_claimed_order_shows_will_not_proceed_once_submitted(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")
        self.event.status = "submitted"
        self.event.save()

        response = self.client.get(self.url)

        self.assertContains(response, "Incomplete, will not proceed")

    def test_no_longer_open_message_absent_when_locked(self):
        self.event.status = "locked"
        self.event.save()

        response = self.client.get(self.url)

        self.assertNotContains(response, "no longer open for claims")

    def test_no_longer_open_message_shown_when_submitted(self):
        self.event.status = "submitted"
        self.event.save()

        response = self.client.get(self.url)

        self.assertContains(response, "no longer open for claims")

    def test_fully_claimed_order_still_shows_full_when_locked(self):
        # 'locked' isn't finalized (it may just be prepping the event before
        # it opens), so a full order shouldn't jump to "Confirmed" yet either.
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=1, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")
        self.event.status = "locked"
        self.event.save()

        response = self.client.get(self.url)

        self.assertContains(response, "Full")
        self.assertNotContains(response, "Confirmed")

    def test_fully_claimed_order_says_confirmed_once_finalized(self):
        item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=1, price="10.00"
        )
        order = Order.objects.create(event=self.event, menu_item=item)
        claim_portions_by_quantity(self.event, [(order.id, 1)], "Alice", "0871234567")
        self.event.status = "submitted"
        self.event.save()

        response = self.client.get(self.url)

        self.assertContains(response, "Confirmed")

    def test_orders_shown_in_creation_order_not_grouped_by_menu_item(self):
        # Names deliberately chosen so alphabetical-by-item-name order (the
        # old grouping behavior) would disagree with creation order.
        item_z = MenuItem.objects.create(
            vendor=self.vendor, name="Zebra Pizza", portions_per_unit=4, price="10.00"
        )
        item_a = MenuItem.objects.create(
            vendor=self.vendor, name="Apple Pizza", portions_per_unit=4, price="10.00"
        )
        Order.objects.create(event=self.event, menu_item=item_z)
        Order.objects.create(event=self.event, menu_item=item_a)

        response = self.client.get(self.url)
        content = response.content.decode()

        self.assertLess(content.index("Zebra Pizza"), content.index("Apple Pizza"))

    def test_no_orders_shows_empty_message(self):
        response = self.client.get(self.url)

        self.assertContains(response, "No orders yet.")

    def test_inactive_menu_item_with_no_orders_not_shown_at_all(self):
        MenuItem.objects.create(
            vendor=self.vendor, name="Discontinued Pizza", portions_per_unit=4, price="10.00",
            is_active=False,
        )

        response = self.client.get(self.url)

        self.assertNotContains(response, "Discontinued Pizza")


class EventOrderSummaryTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        # portions_per_unit=1 so a single claim fully claims the order.
        self.margherita = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=1, price="10.00"
        )
        # portions_per_unit=2 so it can be left partially claimed.
        self.pepperoni = MenuItem.objects.create(
            vendor=self.vendor, name="Pepperoni", portions_per_unit=2, price="12.00"
        )
        self.event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now(),
        )
        full_order_1 = Order.objects.create(event=self.event, menu_item=self.margherita)
        full_order_2 = Order.objects.create(event=self.event, menu_item=self.margherita)
        claim_portions_by_quantity(self.event, [(full_order_1.id, 1)], "Alice", "0871234567")
        claim_portions_by_quantity(self.event, [(full_order_2.id, 1)], "Bob", "0871234568")
        self.partial_order = Order.objects.create(event=self.event, menu_item=self.pepperoni)
        claim_portions_by_quantity(self.event, [(self.partial_order.id, 1)], "Carol", "0871234569")
        self.url = reverse("events:event_detail", args=[self.organisation.slug, self.event.public_id])

    def test_summary_only_counts_fully_claimed_orders(self):
        self.event.status = "submitted"
        self.event.save()

        response = self.client.get(self.url)

        self.assertContains(response, "Order summary")
        self.assertContains(response, "Margherita × 2: €20.00")
        self.assertNotContains(response, "Pepperoni × ")
        self.assertContains(response, "Total: €20.00")

    def test_summary_shown_when_completed(self):
        self.event.status = "completed"
        self.event.save()

        response = self.client.get(self.url)

        self.assertContains(response, "Order summary")
        self.assertContains(response, "Total: €20.00")

    def test_summary_absent_when_open(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, "Order summary")

    def test_summary_absent_when_locked(self):
        self.event.status = "locked"
        self.event.save()

        response = self.client.get(self.url)

        self.assertNotContains(response, "Order summary")

    def test_summary_absent_when_submitted_with_no_orders(self):
        self.event.status = "submitted"
        self.event.save()
        Order.objects.filter(event=self.event).delete()

        response = self.client.get(self.url)

        self.assertNotContains(response, "Order summary")
        self.assertContains(response, "no longer open for claims")

    def test_summary_absent_when_submitted_with_only_partial_orders(self):
        self.event.status = "submitted"
        self.event.save()
        Order.objects.filter(event=self.event).exclude(pk=self.partial_order.pk).delete()

        response = self.client.get(self.url)

        self.assertNotContains(response, "Order summary")


class EventPublicIdTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")

    def test_two_events_get_different_public_ids(self):
        event1 = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now(),
        )
        event2 = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Saturday Lunch",
            deadline=timezone.now(),
        )

        self.assertNotEqual(event1.public_id, event2.public_id)
        self.assertTrue(event1.public_id)
        self.assertTrue(event2.public_id)

    def test_resaving_an_event_does_not_change_its_public_id(self):
        event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Friday Lunch",
            deadline=timezone.now(),
        )
        original_public_id = event.public_id

        event.name = "Friday Lunch (renamed)"
        event.save()

        self.assertEqual(event.public_id, original_public_id)
