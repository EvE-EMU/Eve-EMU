import logging
from typing import ClassVar

from django.db import models

from esi.errors import TokenError
from esi.exceptions import HTTPClientError, HTTPNotModified
from esi.models import Token

from allianceauth.authentication.models import CharacterOwnership, UserProfile
from allianceauth.eveonline.models import (
    EveAllianceInfo, EveCharacter, EveCorporationInfo,
)
from allianceauth.notifications import notify

from .managers import CorpStatsManager
from .providers import (
    get_characters_character_id, get_corporations_corporation_id_members,
    post_universe_names,
)

logger = logging.getLogger(__name__)


class CorpStats(models.Model):
    token = models.ForeignKey(Token, on_delete=models.CASCADE)
    corp = models.OneToOneField(EveCorporationInfo, on_delete=models.CASCADE)
    last_update = models.DateTimeField(auto_now=True)
    members: models.QuerySet["CorpMember"]

    objects: ClassVar[CorpStatsManager] = CorpStatsManager()  # pyright: ignore[reportIncompatibleVariableOverride]

    class Meta:
        permissions = (
            ('view_corp_corpstats', 'Can view corp stats of their corporation.'),
            ('view_alliance_corpstats', 'Can view corp stats of members of their alliance.'),
            ('view_state_corpstats', 'Can view corp stats of members of their auth state.'),
        )
        default_permissions = ('add',)
        verbose_name = "Corp Stat"
        verbose_name_plural = "Corp Stats"

    def __str__(self) -> str:
        return f"{self.__class__.__name__} for {self.corp}"

    def update(self) -> None:
        try:
            assert get_characters_character_id(self.token.character_id).corporation_id == int(self.corp.corporation_id)

            try:
                logger.debug(f"{self} updating members.")

                member_ids = get_corporations_corporation_id_members(corporation_id=self.corp.corporation_id, token=self.token)

                # requesting too many ids per call results in a HTTP400
                # the OpenAPI spec doesn't have a maxItems count
                # manual testing says we can do over 350, but let's not risk it
                member_id_chunks = [member_ids[i:i + 255] for i in range(0, len(member_ids), 255)]
                member_name_chunks = [post_universe_names(ids=id_chunk) for id_chunk in member_id_chunks]
                member_list = {}
                for name_chunk in member_name_chunks:
                    member_list.update({m.id: m.name for m in name_chunk})

                # bulk create new member models
                missing_members = [m_id for m_id in member_ids if not CorpMember.objects.filter(corpstats=self, character_id=m_id).exists()]
                CorpMember.objects.bulk_create(
                    [CorpMember(character_id=m_id, character_name=member_list[m_id], corpstats=self) for m_id in missing_members])

                # purge old members
                self.members.exclude(character_id__in=member_ids).delete()

                # update the timer
                self.save()
            except HTTPNotModified:
                logger.debug(f"{self} data not modified, updating timer.")

                # if the data hasn't changed, we still want to update the timer
                self.save()
        except TokenError as e:
            logger.warning(f"{self} failed to update: {e}")
            if self.token.user:
                notify(
                    self.token.user, f"{self} failed to update with your ESI token.",
                    message="Your token has expired or is no longer valid. Please add a new one to create a new CorpStats.",
                    level="error")
            self.delete()
        except HTTPClientError as e:
            if e.status_code == 403:
                logger.warning(f"{self} failed to update: {e}")
                if self.token.user:
                    notify(self.token.user, f"{self} failed to update with your ESI token.", message=f"{e.status_code}", level="error")
                self.delete()
        except AssertionError:
            logger.warning(f"{self} token character no longer in corp.")
            if self.token.user:
                notify(
                    self.token.user, f"{self} cannot update with your ESI token.",
                    message=f"{self} cannot update with your ESI token as you have left corp.", level="error")
            self.delete()

    @property
    def member_count(self) -> int:
        return self.members.count()

    @property
    def user_count(self) -> int:
        return len({m.main_character for m in self.members.all() if m.main_character})

    @property
    def registered_member_count(self) -> int:
        return len(self.registered_members)

    @property
    def registered_members(self) -> models.QuerySet["CorpMember"]:
        return self.members.filter(pk__in=[m.pk for m in self.members.all() if m.registered])

    @property
    def unregistered_member_count(self) -> int:
        return self.member_count - self.registered_member_count

    @property
    def unregistered_members(self) -> models.QuerySet["CorpMember"]:
        return self.members.filter(pk__in=[m.pk for m in self.members.all() if not m.registered])

    @property
    def main_count(self) -> int:
        return len(self.mains)

    @property
    def mains(self) -> models.QuerySet["CorpMember"]:
        return self.members.filter(pk__in=[m.pk for m in self.members.all() if m.main_character and int(m.main_character.character_id) == int(m.character_id)])

    def visible_to(self, user) -> bool:
        return CorpStats.objects.filter(pk=self.pk).visible_to(user).exists()

    def can_update(self, user) -> bool:
        return self.token.user == user or self.visible_to(user)

    def corp_logo(self, size=128) -> str:
        return self.corp.logo_url(size)

    def alliance_logo(self, size=128) -> str:
        if self.corp.alliance:
            return self.corp.alliance.logo_url(size)
        else:
            return EveAllianceInfo.generic_logo_url(1, size)


class CorpMember(models.Model):
    character_id = models.PositiveIntegerField()
    character_name = models.CharField(max_length=37)
    corpstats = models.ForeignKey(CorpStats, on_delete=models.CASCADE, related_name='members')

    class Meta:
        default_permissions = ()
        verbose_name = "Corp Member"
        verbose_name_plural = "Corp Members"
        # not making character_id unique in case a character moves between two corps while only one updates
        unique_together = ('corpstats', 'character_id')
        ordering = ['character_name']

    def __str__(self) -> str:
        return self.character_name

    @property
    def character(self) -> EveCharacter | None:
        try:
            return EveCharacter.objects.get(character_id=self.character_id)
        except EveCharacter.DoesNotExist:
            return None

    @property
    def main_character(self) -> EveCharacter | None:
        try:
            return self.character.character_ownership.user.profile.main_character
        except (CharacterOwnership.DoesNotExist, UserProfile.DoesNotExist, AttributeError):
            return None

    @property
    def alts(self) -> list["EveCharacter"]:
        if self.main_character:
            return [co.character for co in self.main_character.character_ownership.user.character_ownerships.all()]
        else:
            return []

    @property
    def registered(self) -> bool:
        return CharacterOwnership.objects.filter(character__character_id=self.character_id).exists()

    def portrait_url(self, size=32) -> str:
        return EveCharacter.generic_portrait_url(self.character_id, size)

    @property
    def portrait_url_32(self) -> str:
        return self.portrait_url(32)

    @property
    def portrait_url_64(self) -> str:
        return self.portrait_url(64)

    @property
    def portrait_url_128(self) -> str:
        return self.portrait_url(128)
