# organisations/permissions.py
from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404

from .models import Organisation, OrganisationMembership


def user_can_access_organisation(user, organisation):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return OrganisationMembership.objects.filter(user=user, organisation=organisation).exists()


def organisation_member_required(view_func):
    """
    Wraps a view that takes an `org_slug` kwarg. Anonymous users are
    redirected to login; logged-in users who aren't a member of that
    organisation (and aren't superusers) get a 403.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        organisation = get_object_or_404(Organisation, slug=kwargs.get('org_slug'))

        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())

        if not user_can_access_organisation(request.user, organisation):
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapper
