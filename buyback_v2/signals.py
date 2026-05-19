from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="buybackprogram.Program")
def ensure_pricing_profile(sender, instance, created, **kwargs):
    if not created:
        return
    from buyback_v2.models import ProgramPricingProfile

    ProgramPricingProfile.objects.get_or_create(program=instance)
