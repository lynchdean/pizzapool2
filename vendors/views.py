from django.contrib import messages
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from organisations.models import Organisation
from organisations.permissions import organisation_member_required

from .forms import MenuItemForm, VendorForm
from .models import MenuItem, Vendor


def _get_org_vendor(org_slug, vendor_id):
    return get_object_or_404(Vendor, pk=vendor_id, organisation__slug=org_slug)


def _vendor_detail_context(vendor, org_slug,
                            new_item_form=None, edited_item_id=None, edited_item_form=None):
    new_item_form = new_item_form or MenuItemForm(vendor=vendor)

    item_forms = []
    for item in vendor.menu_items.all():
        if item.id == edited_item_id and edited_item_form is not None:
            item_forms.append((item, edited_item_form))
        else:
            item_forms.append((item, MenuItemForm(instance=item, vendor=vendor)))

    return {
        'org_slug': org_slug,
        'vendor': vendor,
        'item_forms': item_forms,
        'new_item_form': new_item_form,
    }


@organisation_member_required
def vendor_create(request, org_slug):
    organisation = get_object_or_404(Organisation, slug=org_slug)

    if request.method == 'POST':
        form = VendorForm(request.POST, organisation=organisation)
        if form.is_valid():
            vendor = form.save()
            messages.success(request, f"Vendor '{vendor.name}' created.")
            return redirect('organisations:vendor_detail', org_slug=organisation.slug, vendor_id=vendor.id)
    else:
        form = VendorForm(organisation=organisation)

    return render(request, 'vendors/vendor_form.html', {
        'organisation': organisation,
        'form': form,
    })


@organisation_member_required
def vendor_detail(request, org_slug, vendor_id):
    vendor = _get_org_vendor(org_slug, vendor_id)

    return render(request, 'vendors/vendor_detail.html', _vendor_detail_context(vendor, org_slug))


@organisation_member_required
def vendor_edit(request, org_slug, vendor_id):
    vendor = _get_org_vendor(org_slug, vendor_id)

    if request.method == 'POST':
        form = VendorForm(request.POST, instance=vendor, organisation=vendor.organisation)
        if form.is_valid():
            form.save()
            messages.success(request, "Vendor updated.")
            return redirect('organisations:vendor_detail', org_slug=org_slug, vendor_id=vendor.id)
    else:
        form = VendorForm(instance=vendor, organisation=vendor.organisation)

    return render(request, 'vendors/vendor_form.html', {
        'organisation': vendor.organisation,
        'vendor': vendor,
        'form': form,
    })


@organisation_member_required
def vendor_delete(request, org_slug, vendor_id):
    vendor = _get_org_vendor(org_slug, vendor_id)

    if request.method == 'POST':
        try:
            name = vendor.name
            vendor.delete()
            messages.success(request, f"Vendor '{name}' deleted.")
        except ProtectedError:
            messages.error(request, "Can't delete this vendor: it still has events.")

    return redirect('organisations:organisation_detail', org_slug=org_slug)


@organisation_member_required
def menu_item_create(request, org_slug, vendor_id):
    vendor = _get_org_vendor(org_slug, vendor_id)

    if request.method == 'POST':
        form = MenuItemForm(request.POST, vendor=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, "Menu item added.")
            return redirect('organisations:vendor_detail', org_slug=org_slug, vendor_id=vendor_id)
        return render(request, 'vendors/vendor_detail.html',
                       _vendor_detail_context(vendor, org_slug, new_item_form=form))

    return redirect('organisations:vendor_detail', org_slug=org_slug, vendor_id=vendor_id)


@organisation_member_required
def menu_item_edit(request, org_slug, vendor_id, item_id):
    vendor = _get_org_vendor(org_slug, vendor_id)
    item = get_object_or_404(MenuItem, pk=item_id, vendor=vendor)

    if request.method == 'POST':
        form = MenuItemForm(request.POST, instance=item, vendor=vendor)
        if form.is_valid():
            form.save()
            messages.success(request, "Menu item updated.")
            return redirect('organisations:vendor_detail', org_slug=org_slug, vendor_id=vendor_id)
        return render(request, 'vendors/vendor_detail.html', _vendor_detail_context(
            vendor, org_slug, edited_item_id=item.id, edited_item_form=form
        ))

    return redirect('organisations:vendor_detail', org_slug=org_slug, vendor_id=vendor_id)


@organisation_member_required
def menu_item_delete(request, org_slug, vendor_id, item_id):
    vendor = _get_org_vendor(org_slug, vendor_id)
    item = get_object_or_404(MenuItem, pk=item_id, vendor=vendor)

    if request.method == 'POST':
        try:
            name = item.name
            item.delete()
            messages.success(request, f"Menu item '{name}' deleted.")
        except ProtectedError:
            messages.error(request, "Can't delete this menu item: it still has orders.")

    return redirect('organisations:vendor_detail', org_slug=org_slug, vendor_id=vendor_id)
