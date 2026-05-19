import random
import uuid
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone
from eveuniverse.models import EveType

from allianceauth.services.hooks import get_extension_logger

from buybackprogram.models import Contract, Program, Tracking, TrackingItem

logger = get_extension_logger(__name__)


def get_input(text):
    """wrapped input to enable unit testing / patching"""
    return input(text)


class Command(BaseCommand):
    help = "Links tracking objects with old contracts after 1.2.0 update"

    def handle(self, *args, **options):
        self.stdout.write(
            "\033[91mThis command is only for development purposes. It will generate an endless amount of dummy contracts until terminated. Do not use in production enviroment!\033[91m\033[0m"
        )
        user_input = get_input(
            "Are you sure you want to proceed and run the command? (y/N)?"
        )
        if user_input.lower() == "y":
            x = 1

            while True:
                x = x

                net_price = random.randint(1000000, 100000000)

                donation = random.randint(100000, 10000000)

                time = timezone.now() - timedelta(x)

                contract_id = x

                program = Program.objects.first()

                user = User.objects.first()

                tracking_number = "aa-bbp-1234-" + uuid.uuid4().hex[:6].upper()

                # Create or update the found contract
                obj, created = Contract.objects.update_or_create(
                    contract_id=contract_id,
                    defaults={
                        "contract_id": contract_id,
                        "assignee_id": 93337205,
                        "availability": "personal",
                        "date_completed": time,
                        "date_expired": time,
                        "date_issued": time,
                        "for_corporation": 0,
                        "issuer_corporation_id": 93337205,
                        "issuer_id": 93337205,
                        "start_location_id": 123,
                        "price": net_price,
                        "status": "finished",
                        "title": tracking_number,
                        "volume": 100,
                    },
                )

                tracking = Tracking(
                    program=program,
                    issuer_user=user,
                    value=10000000,
                    taxes=500000,
                    hauling_cost=0,
                    donation=donation,
                    contract_id=obj.id,
                    net_price=net_price,
                    tracking_number=tracking_number,
                    created_at=time,
                )

                tracking.save()

                objs = []

                for n in range(0, 3):
                    item_type = EveType.objects.order_by("?").first()

                    tracking_item = TrackingItem(
                        tracking=tracking,
                        eve_type=item_type,
                        buy_value=10,
                        quantity=2,
                    )

                    objs.append(tracking_item)

                TrackingItem.objects.bulk_create(objs)

                x = x + 1

                logger.debug("Generated contract %s" % contract_id)
            else:
                self.stdout.write("Aborted")
