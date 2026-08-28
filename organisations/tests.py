from django.contrib.auth.models import AnonymousUser, User
from django.core import mail
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from vendors.models import Vendor

from .forms import OrganisationForm
from .models import Organisation, OrganisationMembership
from .permissions import organisation_member_required, user_can_access_organisation


@organisation_member_required
def _dummy_view(request, org_slug):
    return HttpResponse("ok")


class OrganisationSlugTests(TestCase):
    def test_slug_auto_generated_from_name(self):
        org = Organisation.objects.create(name="Dean's Office")

        self.assertEqual(org.slug, "deans-office")

    def test_colliding_slugs_get_disambiguated(self):
        org1 = Organisation.objects.create(name="Cafe")
        org2 = Organisation.objects.create(name="Café")

        self.assertEqual(org1.slug, "cafe")
        self.assertEqual(org2.slug, "cafe-2")

    def test_renaming_changes_the_slug(self):
        org = Organisation.objects.create(name="Old Name")
        self.assertEqual(org.slug, "old-name")

        org.name = "New Name"
        org.save()

        self.assertEqual(org.slug, "new-name")

    def test_reserved_name_raises_validation_error(self):
        org = Organisation(name="Orders")

        with self.assertRaises(ValidationError):
            org.full_clean()


class OrganisationCurrencyTests(TestCase):
    def test_new_organisation_defaults_to_eur(self):
        org = Organisation.objects.create(name="Acme")

        self.assertEqual(org.currency, "EUR")
        self.assertEqual(org.currency_symbol, "€")

    def test_currency_symbol_for_each_choice(self):
        self.assertEqual(Organisation(currency="EUR").currency_symbol, "€")
        self.assertEqual(Organisation(currency="GBP").currency_symbol, "£")
        self.assertEqual(Organisation(currency="USD").currency_symbol, "$")

    def test_currency_symbol_falls_back_to_code_for_unrecognized_currency(self):
        org = Organisation(currency="XYZ")

        self.assertEqual(org.currency_symbol, "XYZ")

    def test_organisation_form_accepts_a_currency_change(self):
        org = Organisation.objects.create(name="Acme")

        form = OrganisationForm(data={"name": "Acme", "currency": "USD"}, instance=org)

        self.assertTrue(form.is_valid())
        saved = form.save()
        self.assertEqual(saved.currency, "USD")


class UserCanAccessOrganisationTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="organiser"
        )
        self.other_user = User.objects.create_user(username="other", password="pw")
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )

    def test_true_for_member(self):
        self.assertTrue(user_can_access_organisation(self.member, self.organisation))

    def test_false_for_non_member(self):
        self.assertFalse(user_can_access_organisation(self.other_user, self.organisation))

    def test_true_for_superuser_non_member(self):
        self.assertTrue(user_can_access_organisation(self.superuser, self.organisation))

    def test_false_for_anonymous(self):
        self.assertFalse(user_can_access_organisation(AnonymousUser(), self.organisation))


class OrganisationMemberRequiredDecoratorTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.organisation = Organisation.objects.create(name="Acme")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="organiser"
        )
        self.other_user = User.objects.create_user(username="other", password="pw")

    def test_anonymous_redirected_to_login(self):
        request = self.factory.get("/acme/")
        request.user = AnonymousUser()

        response = _dummy_view(request, org_slug=self.organisation.slug)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_member_gets_permission_denied(self):
        request = self.factory.get("/acme/")
        request.user = self.other_user

        with self.assertRaises(PermissionDenied):
            _dummy_view(request, org_slug=self.organisation.slug)

    def test_member_passes_through(self):
        request = self.factory.get("/acme/")
        request.user = self.member

        response = _dummy_view(request, org_slug=self.organisation.slug)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ok")


class MyOrganisationsViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.other_organisation = Organisation.objects.create(name="Other Co")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("organisations:my_organisations"))

        expected_url = f"{reverse('login')}?next={reverse('organisations:my_organisations')}"
        self.assertRedirects(response, expected_url)

    def test_member_sees_only_their_organisations(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("organisations:my_organisations"))

        self.assertContains(response, "Acme")
        self.assertNotContains(response, "Other Co")

    def test_superuser_sees_all_organisations(self):
        self.client.force_login(self.superuser)

        response = self.client.get(reverse("organisations:my_organisations"))

        self.assertContains(response, "Acme")
        self.assertContains(response, "Other Co")

    def test_links_use_organisation_slug(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("organisations:my_organisations"))

        self.assertContains(response, f'href="/{self.organisation.slug}/"')


class OrganisationDetailViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.other_user = User.objects.create_user(username="other", password="pw")
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="pw"
        )
        self.vendor = Vendor.objects.create(organisation=self.organisation, name="Pizza Place")
        self.event = Event.objects.create(
            organisation=self.organisation,
            vendor=self.vendor,
            name="Friday Lunch",
            deadline=timezone.now(),
        )
        self.url = reverse("organisations:organisation_detail", args=[self.organisation.slug])

    def test_anonymous_can_view_dashboard(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Friday Lunch")

    def test_events_ordered_by_deadline_not_creation_order(self):
        # Created deliberately out of deadline order, so ordering by pk/
        # creation time (the old default) would disagree with this.
        later = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Later Event",
            deadline=timezone.now() + timezone.timedelta(days=5),
        )
        earlier = Event.objects.create(
            organisation=self.organisation, vendor=self.vendor, name="Earlier Event",
            deadline=timezone.now() + timezone.timedelta(days=1),
        )

        response = self.client.get(self.url)
        content = response.content.decode()

        self.assertLess(content.index("Earlier Event"), content.index("Later Event"))

    def test_vendors_list_hidden_for_anonymous_visitors(self):
        response = self.client.get(self.url)

        self.assertNotContains(response, "<strong>Vendors</strong>")
        self.assertNotContains(
            response, reverse("organisations:vendor_detail", args=[self.organisation.slug, self.vendor.id])
        )

    def test_vendors_list_hidden_for_non_members(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertNotContains(response, "<strong>Vendors</strong>")

    def test_vendors_list_shown_to_members(self):
        self.client.force_login(self.member)

        response = self.client.get(self.url)

        self.assertContains(response, "<strong>Vendors</strong>")
        self.assertContains(
            response, reverse("organisations:vendor_detail", args=[self.organisation.slug, self.vendor.id])
        )

    def test_non_member_can_view_dashboard(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_edit_link_hidden_for_anonymous_visitors(self):
        response = self.client.get(self.url)

        self.assertNotContains(
            response, reverse("organisations:organisation_edit", args=[self.organisation.slug])
        )

    def test_edit_link_hidden_for_non_members(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertNotContains(
            response, reverse("organisations:organisation_edit", args=[self.organisation.slug])
        )

    def test_management_controls_hidden_for_anonymous_visitors(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Friday Lunch")
        self.assertNotContains(response, "Add vendor")
        self.assertNotContains(response, "Add event")
        self.assertNotContains(
            response, reverse("organisations:event_edit", args=[self.organisation.slug, self.event.public_id])
        )
        self.assertNotContains(
            response, reverse("organisations:event_delete", args=[self.organisation.slug, self.event.public_id])
        )

    def test_unknown_slug_returns_404(self):
        self.client.force_login(self.member)

        response = self.client.get(reverse("organisations:organisation_detail", args=["no-such-org"]))

        self.assertEqual(response.status_code, 404)

    def test_member_can_view_dashboard(self):
        self.client.force_login(self.member)

        response = self.client.get(self.url)

        self.assertContains(response, "Pizza Place")
        self.assertContains(response, "Friday Lunch")

    def test_superuser_can_view_any_organisation_dashboard(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_dashboard_shows_edit_link(self):
        self.client.force_login(self.member)

        response = self.client.get(self.url)

        self.assertContains(
            response, reverse("organisations:organisation_edit", args=[self.organisation.slug])
        )


class OrganisationEditViewTests(TestCase):
    def setUp(self):
        self.organisation = Organisation.objects.create(name="Acme")
        self.member = User.objects.create_user(username="member", password="pw")
        OrganisationMembership.objects.create(
            user=self.member, organisation=self.organisation, role="owner"
        )
        self.other_user = User.objects.create_user(username="other", password="pw")
        self.url = reverse("organisations:organisation_edit", args=[self.organisation.slug])

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)

        expected_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(response, expected_url)

    def test_non_member_gets_403(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_post_updates_organisation_name_and_redirects_to_new_slug(self):
        self.client.force_login(self.member)

        response = self.client.post(self.url, {"name": "Acme Renamed", "currency": "EUR"})

        new_url = reverse("organisations:organisation_detail", args=["acme-renamed"])
        self.assertRedirects(response, new_url)
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.name, "Acme Renamed")
        self.assertEqual(self.organisation.slug, "acme-renamed")

    def test_post_with_blank_name_shows_form_error_and_leaves_name_unchanged(self):
        self.client.force_login(self.member)

        response = self.client.post(self.url, {"name": ""})

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "name", "This field is required.")
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.name, "Acme")

    def test_post_updates_currency(self):
        self.client.force_login(self.member)

        self.client.post(self.url, {"name": "Acme", "currency": "GBP"})

        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.currency, "GBP")


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="member", password="pw")

    def test_login_page_renders(self):
        response = self.client.get(reverse("login"))

        self.assertEqual(response.status_code, 200)

    def test_login_redirects_to_my_organisations(self):
        response = self.client.post(
            reverse("login"), {"username": "member", "password": "pw"}
        )

        self.assertRedirects(response, reverse("organisations:my_organisations"))

    def test_logout_rejects_get(self):
        response = self.client.get(reverse("logout"))

        self.assertEqual(response.status_code, 405)

    def test_logout_redirects_to_login(self):
        self.client.force_login(self.user)

        response = self.client.post(reverse("logout"))

        self.assertRedirects(response, reverse("login"))


class PasswordResetTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="member", password="old-password", email="member@example.com"
        )

    def test_password_reset_page_renders(self):
        response = self.client.get(reverse("password_reset"))

        self.assertEqual(response.status_code, 200)

    def test_requesting_reset_for_known_email_sends_an_email(self):
        response = self.client.post(reverse("password_reset"), {"email": "member@example.com"})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("member@example.com", mail.outbox[0].to)

    def test_requesting_reset_for_unknown_email_sends_nothing_but_still_redirects(self):
        response = self.client.post(reverse("password_reset"), {"email": "nobody@example.com"})

        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_full_reset_flow_lets_user_log_in_with_new_password(self):
        self.client.post(reverse("password_reset"), {"email": "member@example.com"})
        reset_link = [
            line for line in mail.outbox[0].body.splitlines() if "/accounts/reset/" in line
        ][0].strip()

        confirm_response = self.client.get(reset_link, follow=True)
        set_password_url = confirm_response.redirect_chain[-1][0]

        response = self.client.post(set_password_url, {
            "new_password1": "a-brand-new-password-123",
            "new_password2": "a-brand-new-password-123",
        })

        self.assertRedirects(response, reverse("password_reset_complete"))
        self.assertTrue(
            self.client.login(username="member", password="a-brand-new-password-123")
        )
