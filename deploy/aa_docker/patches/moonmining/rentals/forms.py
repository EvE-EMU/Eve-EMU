"""Forms for lease configuration and admin settings."""

from django import forms
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _

from .models import MoonLease, RentalModuleSettings


class LeaseForm(forms.ModelForm):
    """Lease editor; POC is chosen via autocomplete (hidden main_poc_id)."""

    main_poc_id = forms.IntegerField(
        required=False,
        widget=forms.HiddenInput,
        label=_("Main POC user id"),
    )

    class Meta:
        model = MoonLease
        fields = (
            "monthly_rent_isk",
            "renter_corporation",
            "poc_may_view_fuel",
            "route_structural_alerts",
            "fuel_percent",
            "notes",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.poc_display_name = ""
        if self.instance and self.instance.pk and self.instance.main_poc_id:
            user = self.instance.main_poc
            self.fields["main_poc_id"].initial = user.pk
            self.poc_display_name = user.username
            if hasattr(user, "profile") and user.profile.main_character:
                self.poc_display_name = user.profile.main_character.character_name

    def clean_main_poc_id(self):
        poc_id = self.cleaned_data.get("main_poc_id")
        if not poc_id:
            return None
        if not User.objects.filter(pk=poc_id, is_active=True).exists():
            raise forms.ValidationError(_("Selected user not found."))
        return poc_id

    def save(self, commit=True):
        instance = super().save(commit=False)
        poc_id = self.cleaned_data.get("main_poc_id")
        instance.main_poc_id = poc_id
        if commit:
            instance.save()
            self.save_m2m()
        return instance


class RentalApplicationForm(forms.Form):
    renter_corporation = forms.CharField(max_length=128, label=_("Renter corporation"))
    proposed_rent_isk = forms.IntegerField(min_value=0, label=_("Monthly rent (ISK)"))


class RentalSettingsForm(forms.ModelForm):
    class Meta:
        model = RentalModuleSettings
        fields = (
            "corporation_id",
            "wallet_division",
            "payment_keyword",
            "due_day_of_month",
            "grace_period_days",
            "fuel_alert_threshold_percent",
            "fuel_reference_hours",
            "fuel_webhook_url",
            "payment_webhook_url",
            "esi_token_id",
            "auto_approve_applications",
        )
