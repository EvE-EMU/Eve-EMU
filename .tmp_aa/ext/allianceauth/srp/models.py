from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from allianceauth.eveonline.models import EveCharacter


class SrpFleetMain(models.Model):
    fleet_name = models.CharField(max_length=254, default="")
    fleet_doctrine = models.CharField(max_length=254, default="")
    fleet_time = models.DateTimeField()
    fleet_srp_code = models.CharField(max_length=254, default="")
    fleet_srp_status = models.CharField(max_length=254, default="")
    fleet_commander = models.ForeignKey(EveCharacter, null=True, on_delete=models.SET_NULL)
    fleet_srp_aar_link = models.CharField(max_length=254, default="")

    srpuserrequest_set: models.QuerySet["SrpUserRequest"]

    class Meta:
        permissions = (
            ("access_srp", "Can access SRP module"),
            ("add_srpfleetmain", "Can access SRP module"),
            # Intentionally Commented out
            # AAv0 has these in the Auth_ Content Type
            # ('srp_management', 'Can Approve and Deny SRP requests, Can create an SRP Fleet'),
        )
        default_permissions = ()

    def __str__(self) -> str:
        return self.fleet_name

    @property
    def total_cost(self) -> int:
        return sum(int(r.srp_total_amount) for r in self.srpuserrequest_set.all())

    @property
    def pending_requests(self) -> int:
        return self.srpuserrequest_set.filter(srp_status="Pending").count()


class SrpUserRequest(models.Model):
    class SRPStatusChoices(models.TextChoices):
        PENDING = "Pending", _("Pending")
        APPROVED = "Approved", _("Approved")
        REJECTED = "Rejected", _("Rejected")

    killboard_link = models.CharField(max_length=254, default="")
    after_action_report_link = models.CharField(max_length=254, default="")
    additional_info = models.CharField(max_length=254, default="")
    srp_status = models.CharField(max_length=8, choices=SRPStatusChoices.choices, default=SRPStatusChoices.PENDING)
    srp_total_amount = models.BigIntegerField(default=0)
    character = models.ForeignKey(EveCharacter, null=True, on_delete=models.SET_NULL)
    srp_fleet_main = models.ForeignKey(SrpFleetMain, on_delete=models.CASCADE)
    kb_total_loss = models.BigIntegerField(default=0)
    srp_ship_name = models.CharField(max_length=254, default="")
    post_time = models.DateTimeField(default=timezone.now)

    class Meta:
        default_permissions = ()

    def __str__(self) -> str:
        if self.character is not None:
            return f"{self.character.character_name}'s SRP request for {self.srp_ship_name}"
        return f"DELETED CHARACTER 's SRP request for {self.srp_ship_name}"
