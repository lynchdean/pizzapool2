from django.contrib.auth.models import AnonymousUser, User
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from events.models import Event
from vendors.models import Vendor

from .models import Organisation, OrganisationMembership
from .permissions import organisation_member_required, user_can_access_organisation


@organisation_member_required
def _dummy_view(request, organisation_id):
    return HttpResponse("ok")


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
        request = self.factory.get("/organisations/1/")
        request.user = AnonymousUser()

        response = _dummy_view(request, organisation_id=self.organisation.id)

        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_non_member_gets_permission_denied(self):
        request = self.factory.get("/organisations/1/")
        request.user = self.other_user

        with self.assertRaises(PermissionDenied):
            _dummy_view(request, organisation_id=self.organisation.id)

    def test_member_passes_through(self):
        request = self.factory.get("/organisations/1/")
        request.user = self.member

        response = _dummy_view(request, organisation_id=self.organisation.id)

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
        self.url = reverse("organisations:organisation_detail", args=[self.organisation.id])

    def test_anonymous_redirected_to_login(self):
        response = self.client.get(self.url)

        expected_url = f"{reverse('login')}?next={self.url}"
        self.assertRedirects(response, expected_url)

    def test_non_member_gets_403(self):
        self.client.force_login(self.other_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_member_can_view_dashboard(self):
        self.client.force_login(self.member)

        response = self.client.get(self.url)

        self.assertContains(response, "Pizza Place")
        self.assertContains(response, "Friday Lunch")

    def test_superuser_can_view_any_organisation_dashboard(self):
        self.client.force_login(self.superuser)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

    def test_post_updates_organisation_name(self):
        self.client.force_login(self.member)

        response = self.client.post(self.url, {"name": "Acme Renamed"})

        self.assertRedirects(response, self.url)
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.name, "Acme Renamed")

    def test_post_with_blank_name_shows_form_error_and_leaves_name_unchanged(self):
        self.client.force_login(self.member)

        response = self.client.post(self.url, {"name": ""})

        self.assertEqual(response.status_code, 200)
        self.assertFormError(response.context["form"], "name", "This field is required.")
        self.organisation.refresh_from_db()
        self.assertEqual(self.organisation.name, "Acme")


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
