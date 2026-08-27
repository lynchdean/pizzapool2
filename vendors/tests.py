from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from orders.models import Order
from organisations.models import Organisation, OrganisationMembership

from .models import MenuItem, Vendor


class VendorCreateViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.other_user = User.objects.create_user(username="other", password="pw")
        self.url = reverse("organisations:vendor_create", args=[self.organisation.slug])

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)

        expected_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(response, expected_url)

    def test_non_member_gets_403(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_member_can_create_vendor(self):
        self.client.force_login(self.member)

        response = self.client.post(self.url, {"name": "Pizza Place", "contact_info": "call me"})

        vendor = Vendor.objects.get(name="Pizza Place")
        self.assertEqual(vendor.organisation, self.organisation)
        self.assertRedirects(
            response,
            reverse("organisations:vendor_detail", args=[self.organisation.slug, vendor.id]),
        )

    def test_duplicate_name_in_same_org_shows_form_error_not_500(self):
        Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.client.force_login(self.member)

        response = self.client.post(self.url, {"name": "Pizza Place", "contact_info": ""})

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["form"], "name",
            "A vendor with this name already exists in this organisation.",
        )
        self.assertEqual(Vendor.objects.filter(organisation=self.organisation).count(), 1)


class VendorDetailViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.other_organisation = Organisation.objects.create(name="Other Co")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.other_user = User.objects.create_user(username="other", password="pw")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.item = MenuItem.objects.create(
            vendor=self.vendor, name="Margherita", portions_per_unit=4, price="10.00"
        )
        self.url = reverse("organisations:vendor_detail", args=[self.organisation.slug, self.vendor.id])

    def test_non_member_gets_403(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_shows_vendor_and_its_menu_items(self):
        self.client.force_login(self.member)

        response = self.client.get(self.url)

        self.assertContains(response, "Pizza Place")
        self.assertContains(response, "Margherita")

    def test_shows_edit_link(self):
        self.client.force_login(self.member)

        response = self.client.get(self.url)

        self.assertContains(
            response,
            reverse("organisations:vendor_edit", args=[self.organisation.slug, self.vendor.id]),
        )

    def test_vendor_belonging_to_other_organisation_returns_404(self):
        # Member of BOTH orgs, so the outer organisation_member_required check
        # passes — this isolates the inner IDOR-scoped lookup in the view.
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.other_organisation, role="owner"
        )
        self.client.force_login(self.member)
        other_org_url = reverse(
            "organisations:vendor_detail", args=[self.other_organisation.slug, self.vendor.id]
        )

        response = self.client.get(other_org_url)

        self.assertEqual(response.status_code, 404)


class VendorEditViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.other_user = User.objects.create_user(username="other", password="pw")
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.url = reverse("organisations:vendor_edit", args=[self.organisation.slug, self.vendor.id])

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)

        expected_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(response, expected_url)

    def test_non_member_gets_403(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_post_updates_vendor_fields(self):
        self.client.force_login(self.member)

        response = self.client.post(self.url, {"name": "Pizza Place Renamed", "contact_info": "x"})

        detail_url = reverse(
            "organisations:vendor_detail", args=[self.organisation.slug, self.vendor.id]
        )
        self.assertRedirects(response, detail_url)
        self.vendor.refresh_from_db()
        self.assertEqual(self.vendor.name, "Pizza Place Renamed")


class VendorDeleteViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")

    def test_deletes_vendor_with_no_events(self):
        self.client.force_login(self.member)
        url = reverse("organisations:vendor_delete", args=[self.organisation.slug, self.vendor.id])

        response = self.client.post(url)

        self.assertRedirects(
            response, reverse("organisations:organisation_detail", args=[self.organisation.slug])
        )
        self.assertFalse(Vendor.objects.filter(pk=self.vendor.id).exists())

    def test_protected_error_when_vendor_has_events_shows_message_and_survives(self):
        Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Lunch", deadline=timezone.now()
        )
        self.client.force_login(self.member)
        url = reverse("organisations:vendor_delete", args=[self.organisation.slug, self.vendor.id])

        response = self.client.post(url, follow=True)

        self.assertContains(response, "still has events")
        self.assertTrue(Vendor.objects.filter(pk=self.vendor.id).exists())


class MenuItemViewTests(TestCase):
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
        self.client.force_login(self.member)

    def test_create_menu_item(self):
        url = reverse("organisations:menu_item_create", args=[self.organisation.slug, self.vendor.id])

        response = self.client.post(
            url, {"name": "Pepperoni", "portions_per_unit": 8, "price": "15.00", "is_active": "on"}
        )

        self.assertRedirects(
            response, reverse("organisations:vendor_detail", args=[self.organisation.slug, self.vendor.id])
        )
        self.assertTrue(MenuItem.objects.filter(vendor=self.vendor, name="Pepperoni").exists())

    def test_duplicate_name_for_same_vendor_shows_form_error(self):
        url = reverse("organisations:menu_item_create", args=[self.organisation.slug, self.vendor.id])

        response = self.client.post(
            url, {"name": "Margherita", "portions_per_unit": 4, "price": "10.00", "is_active": "on"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertFormError(
            response.context["new_item_form"], "name",
            "A menu item with this name already exists for this vendor.",
        )
        self.assertEqual(MenuItem.objects.filter(vendor=self.vendor, name="Margherita").count(), 1)

    def test_edit_menu_item(self):
        url = reverse(
            "organisations:menu_item_edit", args=[self.organisation.slug, self.vendor.id, self.item.id]
        )

        response = self.client.post(
            url, {"name": "Margherita Deluxe", "portions_per_unit": 4, "price": "12.00", "is_active": "on"}
        )

        self.assertRedirects(
            response, reverse("organisations:vendor_detail", args=[self.organisation.slug, self.vendor.id])
        )
        self.item.refresh_from_db()
        self.assertEqual(self.item.name, "Margherita Deluxe")

    def test_delete_menu_item_with_no_orders(self):
        url = reverse(
            "organisations:menu_item_delete", args=[self.organisation.slug, self.vendor.id, self.item.id]
        )

        response = self.client.post(url)

        self.assertRedirects(
            response, reverse("organisations:vendor_detail", args=[self.organisation.slug, self.vendor.id])
        )
        self.assertFalse(MenuItem.objects.filter(pk=self.item.id).exists())

    def test_protected_error_when_menu_item_has_orders_shows_message_and_survives(self):
        event = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Lunch", deadline=timezone.now()
        )
        Order.objects.create(event=event, menu_item=self.item)
        url = reverse(
            "organisations:menu_item_delete", args=[self.organisation.slug, self.vendor.id, self.item.id]
        )

        response = self.client.post(url, follow=True)

        self.assertContains(response, "still has orders")
        self.assertTrue(MenuItem.objects.filter(pk=self.item.id).exists())
