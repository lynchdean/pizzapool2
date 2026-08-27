from django import forms
from django.utils import timezone

from vendors.models import Vendor

from .models import Event


class EventForm(forms.ModelForm):
    class Meta:
        model = Event
        fields = ['vendor', 'name', 'status', 'deadline']

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organisation = organisation or (self.instance.organisation if self.instance.pk else None)
        self.fields['vendor'].queryset = Vendor.objects.filter(organisation=self.organisation)

        if self.instance.pk and self.instance.orders.exists():
            self.fields['vendor'].disabled = True
            self.fields['vendor'].help_text = "Can't change vendor once orders exist for this event."

    def clean_deadline(self):
        deadline = self.cleaned_data['deadline']
        if not self.instance.pk and deadline <= timezone.now():
            raise forms.ValidationError("Deadline must be in the future.")
        return deadline

    def save(self, commit=True):
        event = super().save(commit=False)
        if self.organisation is not None:
            event.organisation = self.organisation
        if commit:
            event.save()
        return event
