from django import forms
from django.core.validators import RegexValidator
from phonenumber_field.formfields import PhoneNumberField


class _ClaimFieldsMixin(forms.Form):
    claimant_name = forms.CharField(max_length=255, label="Your name")
    claimant_phone = PhoneNumberField(label="Phone number")
    quantity = forms.IntegerField(min_value=1)

    def __init__(self, *args, max_quantity=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.max_quantity = max_quantity

    def clean_quantity(self):
        value = self.cleaned_data['quantity']
        if self.max_quantity is not None and value > self.max_quantity:
            raise forms.ValidationError(f"Only {self.max_quantity} available.")
        return value


class JoinOrderForm(_ClaimFieldsMixin):
    pass


class StartOrderForm(_ClaimFieldsMixin):
    # Revolut's own Revtag rules: 3-16 characters, letters/numbers only.
    revolut_username = forms.CharField(
        min_length=3, max_length=16, label="Your Revolut username",
        help_text="So others can pay you back.",
        validators=[RegexValidator(
            regex=r'^[A-Za-z0-9]+$',
            message="Revolut usernames can only contain letters and numbers.",
        )],
    )


class UnclaimForm(forms.Form):
    claimant_phone = PhoneNumberField(label="Phone number")
