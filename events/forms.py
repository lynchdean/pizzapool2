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
        fields = ['vendor', 'name', 'description', 'status', 'deadline']

    def __init__(self, *args, organisation=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.organisation = organisation or (self.instance.organisation if self.instance.pk else None)
        self.fields['vendor'].queryset = Vendor.objects.filter(organisation=self.organisation)

        if self.instance.pk and self.instance.orders.exists():
            self.fields['vendor'].disabled = True
            self.fields['vendor'].help_text = "Can't change vendor once orders exist for this event."

    def clean(self):
        cleaned_data = super().clean()
        deadline = cleaned_data.get('deadline')
        status = cleaned_data.get('status')

        # Required for brand-new events regardless of status, and for any
        # event (new or existing) being saved as 'open' - reopening a
        # past-deadline event without pushing the deadline forward would
        # immediately be blocked by orders/services.py's deadline check
        # anyway, and the next page load's auto-close would flip it right
        # back to 'closed'. Pushing the deadline forward is the actual "give
        # it a final window" action, not a side detail.
        if deadline is not None and deadline <= timezone.now():
            if not self.instance.pk:
                self.add_error('deadline', "Deadline must be in the future.")
            elif status == 'open':
                self.add_error('deadline', "Deadline must be in the future to reopen this event.")

        return cleaned_data

    def save(self, commit=True):
        event = super().save(commit=False)
        if self.organisation is not None:
            event.organisation = self.organisation
        if commit:
            event.save()
        return event
