from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator


class PublicCalculatorForm(forms.Form):
    items = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 12, "class": "form-control"}),
        label="Items",
        help_text="Paste item lines from your EVE inventory (tab-separated).",
    )
    donation = forms.IntegerField(
        label="Donation %",
        initial=0,
        required=False,
        validators=[MaxValueValidator(100), MinValueValidator(0)],
    )
