# Third Party
from modeltranslation.translator import TranslationOptions, translator

from .models.map import Constellation, Moon, NPCStation, Planet, Region, SolarSystem
from .models.types import (
    DogmaAttribute,
    DogmaEffect,
    DogmaUnit,
    ItemCategory,
    ItemGroup,
    ItemMarketGroup,
    ItemType,
)


class NameAndDescriptionTranslationOptions(TranslationOptions):
    fields = ('name', 'description')


translator.register(Region, NameAndDescriptionTranslationOptions)
translator.register(ItemMarketGroup, NameAndDescriptionTranslationOptions)
translator.register(ItemType, NameAndDescriptionTranslationOptions)


class NameTranslationOptions(TranslationOptions):
    fields = ('name', )


translator.register(Constellation, NameTranslationOptions)
translator.register(SolarSystem, NameTranslationOptions)
translator.register(NPCStation, NameTranslationOptions)
translator.register(Planet, NameTranslationOptions)
translator.register(Moon, NameTranslationOptions)
translator.register(ItemCategory, NameTranslationOptions)
translator.register(ItemGroup, NameTranslationOptions)


class DogmaUnitTranslationOptions(TranslationOptions):
    fields = ('display_name', 'description')


translator.register(DogmaUnit, DogmaUnitTranslationOptions)


class DogmaAttributeTranslationOptions(TranslationOptions):
    fields = ('tooltip_description', 'tooltip_title', 'display_name')


translator.register(DogmaAttribute, DogmaAttributeTranslationOptions)


class DogmaEffectTranslationOptions(TranslationOptions):
    fields = ("display_name", "description")


translator.register(DogmaEffect, DogmaEffectTranslationOptions)
