from django import forms

from .models import MenuItem, Vendor


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['name', 'contact_info']

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organisation = organisation or (self.instance.organisation if self.instance.pk else None)

    def clean_name(self):
        name = self.cleaned_data['name']
        qs = Vendor.objects.filter(organisation=self.organisation, name=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A vendor with this name already exists in this organisation.")
        return name

    def save(self, commit=True):
        vendor = super().save(commit=False)
        vendor.organisation = self.organisation
        if commit:
            vendor.save()
        return vendor


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ['name', 'portions_per_unit', 'price', 'is_active']

    def __init__(self, *args, vendor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.vendor = vendor or (self.instance.vendor if self.instance.pk else None)

    def clean_name(self):
        name = self.cleaned_data['name']
        qs = MenuItem.objects.filter(vendor=self.vendor, name=name)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("A menu item with this name already exists for this vendor.")
        return name

    def clean_portions_per_unit(self):
        value = self.cleaned_data['portions_per_unit']
        if value < 1:
            raise forms.ValidationError("Must be at least 1.")
        return value

    def clean_price(self):
        value = self.cleaned_data['price']
        if value <= 0:
            raise forms.ValidationError("Price must be greater than zero.")
        return value

    def save(self, commit=True):
        item = super().save(commit=False)
        item.vendor = self.vendor
        if commit:
            item.save()
        return item
