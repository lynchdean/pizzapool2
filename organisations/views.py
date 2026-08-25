from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import OrganisationForm
from .models import Organisation, OrganisationMembership
from .permissions import organisation_member_required


@login_required
def my_organisations(request):
    if request.user.is_superuser:
        organisations = [
            {'organisation': org, 'role': None}
            for org in Organisation.objects.all()
        ]
    else:
        organisations = [
            {'organisation': membership.organisation, 'role': membership.get_role_display()}
            for membership in OrganisationMembership.objects
                .filter(user=request.user)
                .select_related('organisation')
        ]

    return render(request, 'organisations/my_organisations.html', {
        'organisations': organisations,
    })


@organisation_member_required
def organisation_detail(request, organisation_id):
    organisation = get_object_or_404(Organisation, pk=organisation_id)

    if request.method == 'POST':
        form = OrganisationForm(request.POST, instance=organisation)
        if form.is_valid():
            form.save()
            messages.success(request, "Organisation updated.")
            return redirect('organisations:organisation_detail', organisation_id=organisation.id)
    else:
        form = OrganisationForm(instance=organisation)

    return render(request, 'organisations/organisation_detail.html', {
        'organisation': organisation,
        'form': form,
        'vendors': organisation.vendors.all(),
        'events': organisation.events.select_related('vendor').all(),
    })
