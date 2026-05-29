# Shamelessly stolen from Member Audit
from eve_sde.models import ItemType, ItemTypeMaterials

from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from allianceauth.services.hooks import get_extension_logger
from app_utils.logging import LoggerAddTag

from .. import __title__
from ..app_settings import (
    MININGTAXES_ALWAYS_TAX_REFINED,
    MININGTAXES_REFINED_RATE,
    MININGTAXES_UNKNOWN_TAX_RATE,
)

logger = LoggerAddTag(get_extension_logger(__name__), __title__)


def get_tax(eve_type):
    try:
        ore = OrePrices.objects.get(eve_type=eve_type)
        return ore.tax_rate / 100.0
    except OrePrices.DoesNotExist:
        pass
    return MININGTAXES_UNKNOWN_TAX_RATE


def ore_calc_prices(eve_type, q):
    try:
        ore = OrePrices.objects.get(eve_type=eve_type)
        return q * ore.raw_price, q * ore.refined_price, q * ore.taxed_price
    except OrePrices.DoesNotExist:
        pass
    quantity = q
    raw_price = quantity * get_price(eve_type)
    materials = ItemTypeMaterials.objects.filter(item_type_id=eve_type.id)
    refined_price = 0.0
    for mat in materials:
        if mat.quantity is None:
            continue
        q = MININGTAXES_REFINED_RATE * (mat.quantity * quantity) / eve_type.portion_size
        refined_price += q * get_price(mat.material_item_type)
    if refined_price == 0.0:
        refined_price = raw_price
    taxed_value = refined_price
    if not MININGTAXES_ALWAYS_TAX_REFINED and raw_price > taxed_value:
        taxed_value = raw_price
    return raw_price, refined_price, taxed_value


def get_price(eve_type):
    ore = None
    try:
        ore = OrePrices.objects.get(eve_type=eve_type)
    except ObjectDoesNotExist:
        pass
    if ore is None:
        mp = eve_type.base_price
        if mp is None:
            return 0.0
        return mp
    return ore.buy


class OrePrices(models.Model):
    eve_type = models.OneToOneField(
        ItemType,
        on_delete=models.deletion.CASCADE,
        unique=True,
    )
    buy = models.FloatField()
    sell = models.FloatField()
    raw_price = models.FloatField(default=0.0)
    refined_price = models.FloatField(default=0.0)
    taxed_price = models.FloatField(default=0.0)
    tax_rate = models.FloatField(default=10.0)
    updated = models.DateTimeField()

    def calc_prices(self):
        self.raw_price = self.buy
        materials = ItemTypeMaterials.objects.filter(item_type_id=self.eve_type.id)

        self.refined_price = 0.0
        for mat in materials:
            if mat.quantity is None:
                continue
            q = MININGTAXES_REFINED_RATE * mat.quantity / self.eve_type.portion_size
            self.refined_price += q * get_price(mat.material_item_type)
        if self.refined_price == 0.0:
            self.refined_price = self.raw_price
        self.taxed_price = self.refined_price
        if not MININGTAXES_ALWAYS_TAX_REFINED and self.raw_price > self.taxed_price:
            self.taxed_price = self.raw_price
        self.save()
