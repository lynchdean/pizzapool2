from django import forms
from django.utils import timezone

from vendors.models import Vendor

from .models import Event


class EventForm(forms.ModelForm):
    # Native browser date/time picker instead of a free-text field the user
    # has to guess the format for. Browsers submit datetime-local values as
    # "YYYY-MM-DDTHH:MM", which isn't in Django's default input_formats, so
    # it's added alongside the pre-existing space-separated formats (still
    # accepted so nothing else that posts a deadline needs to change).
    deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'],
    )

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
