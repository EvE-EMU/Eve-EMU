from django import forms

from corp_orders.models import FreightOrder
from corp_orders.services.systems import resolve_solar_system_name


class QuoteForm(forms.Form):
    items_text = forms.CharField(
        label="Inventory paste",
        widget=forms.Textarea(
            attrs={
                "rows": 12,
                "class": "form-control font-monospace",
                "placeholder": "Copy from in-game inventory (Ctrl+C) — tab-separated lines",
            }
        ),
    )
    final_destination_system = forms.CharField(
        label="Final destination system",
        max_length=64,
        widget=forms.TextInput(
            attrs={
                "class": "form-control corp-orders-system-input",
                "placeholder": "Type to search systems…",
                "autocomplete": "off",
                "spellcheck": "false",
            }
        ),
        help_text="Start typing a system name or pick from the list. Freight is quoted to the hub (Badivefi) only.",
    )

    def clean_final_destination_system(self):
        name = (self.cleaned_data.get("final_destination_system") or "").strip()
        if not name:
            raise forms.ValidationError("Enter a destination system name.")
        if not resolve_solar_system_name(name):
            raise forms.ValidationError(
                f'"{name}" is not a known solar system — pick one from the dropdown.'
            )
        return name
    speed = forms.ChoiceField(
        label="Delivery speed",
        choices=FreightOrder.Speed.choices,
        initial=FreightOrder.Speed.REGULAR,
        widget=forms.RadioSelect,
    )
    issuer_kind = forms.ChoiceField(
        label="Contract issuer",
        choices=FreightOrder.IssuerKind.choices,
        initial=FreightOrder.IssuerKind.CHARACTER,
        widget=forms.RadioSelect,
    )
    wallet_method = forms.ChoiceField(
        label="Payback wallet",
        choices=FreightOrder.WalletMethod.choices,
        initial=FreightOrder.WalletMethod.CORP_WALLET,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    wallet_notes = forms.CharField(
        required=False,
        label="Wallet notes",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Optional"}),
    )
    payback_on_completion = forms.BooleanField(
        required=False,
        label="Notify payback when contract completes (personal wallet)",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
    )


class LinkContractForm(forms.Form):
    eve_contract_id = forms.IntegerField(
        label="EVE contract ID",
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
