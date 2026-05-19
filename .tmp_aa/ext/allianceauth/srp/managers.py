import logging

import requests

from django.contrib.auth.models import User

from allianceauth import __title_useragent__, __url__, __version__

from .models import SrpUserRequest
from .providers import get_killmails_killmail_id_killmail_hash

logger = logging.getLogger(__name__)


class SRPManager:

    @staticmethod
    def get_kill_id(killboard_link):
        num_set = '0123456789'
        kill_id = ''.join([c for c in killboard_link if c in num_set])
        return kill_id

    @staticmethod
    def get_kill_data(kill_id):
        url = (f"https://zkillboard.com/api/killID/{kill_id}/")
        headers = {
            'User-Agent': f'{__title_useragent__}/{__version__} (+{__url__})',
            'Content-Type': 'application/json',
        }
        r = requests.get(url, headers=headers)
        result = r.json()[0]
        if result:
            killmail_id = result['killmail_id']
            killmail_hash = result['zkb']['hash']
            km = get_killmails_killmail_id_killmail_hash(killmail_id=killmail_id, killmail_hash=killmail_hash)
        else:
            raise ValueError("Invalid Kill ID")
        if km:
            ship_type = km.victim.ship_type_id
            logger.debug(
                f"Ship type for kill ID {kill_id} is {ship_type}"
            )
            ship_value = result['zkb']['totalValue']
            logger.debug(
                f"Total loss value for kill id {kill_id} is {ship_value}"
            )
            victim_id = km.victim.character_id
            return ship_type, ship_value, victim_id
        else:
            raise ValueError("Invalid Kill ID or Hash.")

    @staticmethod
    def pending_requests_count_for_user(user: User):
        """returns the number of open SRP requests for given user
        or None if user has no permission"""
        if user.has_perm("auth.srp_management"):
            return SrpUserRequest.objects.filter(srp_status="Pending").count()
        else:
            return None
