import datetime as dt

from discordproxy.discord_api_pb2 import Channel
from memberaudit.models import CharacterMail, MailEntity
from pytz import utc

from django.contrib.auth.models import User
from eveuniverse.models import EveEntity

from mailrelay.models import DiscordCategory, DiscordChannel, RelayConfig


class FakeRequest(object):
    def __init__(self, user=None):
        self.user = user


def id_generator() -> int:
    seed = 1
    while True:
        yield seed
        seed += 1


unique_ids = id_generator()


def create_eve_entity(**kwargs) -> EveEntity:
    if "category" not in kwargs:
        kwargs["category"] = EveEntity.CATEGORY_CHARACTER
    return EveEntity.objects.create(**kwargs)


def create_eve_entities_from_evecharacter(character):
    create_eve_entity(
        id=character.character_id,
        name=character.character_name,
        category=EveEntity.CATEGORY_CHARACTER,
    )
    create_eve_entity(
        id=character.corporation_id,
        name=character.corporation_name,
        category=EveEntity.CATEGORY_CORPORATION,
    )
    if character.alliance_id:
        create_eve_entity(
            id=character.alliance_id,
            name=character.alliance_name,
            category=EveEntity.CATEGORY_ALLIANCE,
        )


def create_character_mail(sender_id, recipient_ids=None, **kwargs) -> CharacterMail:
    if "timestamp" not in kwargs:
        kwargs["timestamp"] = dt.datetime(2021, 12, 24, 12, 15, tzinfo=utc)
    if not recipient_ids:
        recipient_ids = []
    if "character" not in kwargs:
        raise ValueError("character parameter not provided")
    character = kwargs["character"]
    sender, _ = MailEntity.objects.update_or_create_from_eve_entity_id(id=sender_id)
    mail_id = next(unique_ids)
    if "body" not in kwargs:
        kwargs["body"] = f"body #{mail_id}"
    kwargs.update(
        {
            "subject": f"subject #{mail_id}",
            "is_read": False,
            "mail_id": mail_id,
            "sender": sender,
        }
    )
    mail = CharacterMail.objects.create(**kwargs)
    recipient_ids += [character.eve_character.character_id]
    recipient_objs = [
        MailEntity.objects.update_or_create_from_eve_entity_id(id=recipient_id)[0]
        for recipient_id in recipient_ids
    ]
    mail.recipients.add(*recipient_objs)
    return mail


def create_relay_config(**kwargs):
    if "mail_category" not in kwargs:
        kwargs["mail_category"] = RelayConfig.MailCategory.ALL
    if "discord_channel" not in kwargs:
        kwargs["discord_channel"] = create_discord_channel(name="test")
    config = RelayConfig.objects.create(**kwargs)

    return config


def create_discord_channel(**kwargs):
    kwargs["id"] = next(unique_ids)
    return DiscordChannel.objects.create(**kwargs)


def create_discord_category(**kwargs):
    kwargs["id"] = next(unique_ids)
    return DiscordCategory.objects.create(**kwargs)


def create_superuser(**kwargs):
    return User.objects.create_superuser(**kwargs)


def create_fake_request(**kwargs):
    return FakeRequest(**kwargs)


# Discordproxy


def create_discordproxy_channel(**kwargs) -> Channel:
    if "id" not in kwargs:
        kwargs["id"] = next(unique_ids)
    if "type" not in kwargs:
        kwargs["type"] = Channel.Type.GUILD_TEXT
    return Channel(**kwargs)
