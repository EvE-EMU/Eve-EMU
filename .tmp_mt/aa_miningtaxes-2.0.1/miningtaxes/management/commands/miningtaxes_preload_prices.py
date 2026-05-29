import requests
from tqdm import tqdm

from django.core.management.base import BaseCommand

from ...helpers import PriceGroups
from ...models import OrePrices, Stats
from ...tasks import update_all_prices


class Command(BaseCommand):
    help = "Uses EVERef to look for all ore groups and ore children"

    def handle(self, *args, **options):
        baseurl = "https://ref-data.everef.net"
        tids = []
        newtids = []
        print("Gathering info on groups")
        for g in tqdm(PriceGroups.groups):
            r = requests.get(f"{baseurl}/groups/{g}").json()
            tids += r["type_ids"]

        print("Gathering info on all typeIDs")
        for t in tqdm(tids):
            r = requests.get(f"{baseurl}/types/{t}").json()
            if "Compressed " in r["name"]["en"]:
                continue
            try:
                OrePrices.objects.get(eve_type_id=t)
            except OrePrices.DoesNotExist:
                newtids.append(t)
                pass
        print(f"Found {len(newtids)} to force add")
        print("Running update")
        update_all_prices(force=newtids)
        print("Updating Ore Chart")
        s = Stats.load()
        s.calc_ore_prices_json()
