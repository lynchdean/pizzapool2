from django import forms
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
    pass
