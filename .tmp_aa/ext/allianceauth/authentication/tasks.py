import logging

from celery import shared_task

from esi.errors import IncompleteResponseError, TokenExpiredError, TokenInvalidError
from esi.models import Token

from allianceauth.authentication.models import CharacterOwnership

logger = logging.getLogger(__name__)


@shared_task
def check_character_ownership(owner_hash):
    tokens = Token.objects.filter(character_owner_hash=owner_hash)
    if tokens:
        for t in tokens:
            old_hash = t.character_owner_hash
            try:
                t.update_token_data(commit=False)
            except (TokenExpiredError, TokenInvalidError):
                t.delete()
                continue
            except (KeyError, IncompleteResponseError):
                # We can't validate the hash hasn't changed but also can't assume it has. Abort for now.
                logger.warning(f"Failed to validate owner hash of {tokens[0].character_name} due to problems contacting SSO servers.")
                break

            if not t.character_owner_hash == old_hash:
                logger.info(
                    f'Character {t.character_name} has changed ownership. Revoking {tokens.count()} tokens.')
                tokens.delete()
            break

    if not Token.objects.filter(character_owner_hash=owner_hash).exists():
        logger.info(f'No tokens found with owner hash {owner_hash}. Revoking ownership.')
        CharacterOwnership.objects.filter(owner_hash=owner_hash).delete()


@shared_task
def check_all_character_ownership():
    for c in CharacterOwnership.objects.all().only('owner_hash'):
        check_character_ownership.delay(c.owner_hash)
