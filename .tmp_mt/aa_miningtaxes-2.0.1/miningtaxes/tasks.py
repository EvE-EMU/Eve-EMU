import requests
from celery import chord, shared_task
from eve_sde.models import ItemType, ItemTypeMaterials

from django.contrib.auth.models import Permission
from django.db import Error
from django.http.response import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from esi.errors import TokenError

from allianceauth.eveonline.models import EveCharacter
from allianceauth.notifications import notify
from allianceauth.services.hooks import get_extension_logger
from app_utils.django import users_with_permission

from .app_settings import (
    MININGTAXES_PING_CURRENT_MSG,
    MININGTAXES_PING_CURRENT_THRESHOLD,
    MININGTAXES_PING_FIRST_MSG,
    MININGTAXES_PING_INTEREST_APPLIED,
    MININGTAXES_PING_SECOND_MSG,
    MININGTAXES_PING_THRESHOLD,
    MININGTAXES_PRICE_JANICE_API_KEY,
    MININGTAXES_PRICE_JANICE_BUY,
    MININGTAXES_PRICE_JANICE_SELL,
    MININGTAXES_PRICE_JANICE_TIMING,
    MININGTAXES_PRICE_METHOD,
    MININGTAXES_PRICE_SOURCE_ID,
    MININGTAXES_PRICE_SOURCE_NAME,
    MININGTAXES_TASKS_TIME_LIMIT,
    MININGTAXES_TAX_ONLY_CORP_MOONS,
)
from .helpers import PriceGroups
from .models import (
    AdminCharacter,
    AdminMiningCorpLedgerEntry,
    AdminMiningObsLog,
    Character,
    CharacterMiningLedgerEntry,
    OrePrices,
    Settings,
    Stats,
)

logger = get_extension_logger(__name__)
TASK_DEFAULT_KWARGS = {"time_limit": MININGTAXES_TASKS_TIME_LIMIT, "max_retries": 3}


def calctaxes():
    s = Stats.load()
    return s.calctaxes()


def get_user(cid):
    try:
        c = EveCharacter.objects.get(character_id=cid)
        p = c.character_ownership.user.profile
    except Exception:
        return None
    if p is None or p.main_character is None:
        return None
    found = None
    for c in p.user.character_ownerships.all():
        try:
            payee = get_object_or_404(Character, eve_character_id=c.character.pk)
        except Exception:
            continue
        found = payee
        break
    return found


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def notify_taxes_due(self):
    user2taxes = calctaxes()

    for u in user2taxes.keys():
        if user2taxes[u][0] > MININGTAXES_PING_THRESHOLD:
            title = "Taxes are due!"
            message = MININGTAXES_PING_FIRST_MSG.format(user2taxes[u][0])
            notify(user=u, title=title, message=message, level="INFO")


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def notify_second_taxes_due(self):
    user2taxes = calctaxes()

    for u in user2taxes.keys():
        if user2taxes[u][0] > MININGTAXES_PING_THRESHOLD:
            title = "Taxes are due!"
            message = MININGTAXES_PING_SECOND_MSG.format(user2taxes[u][0])
            notify(user=u, title=title, message=message, level="INFO")


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def notify_current_taxes_threshold(self):
    from django.contrib.auth.models import User

    from .models import Stats

    s = Stats.load()
    arr = s.get_admin_main_json()

    for row in arr:
        if row["balance"] >= MININGTAXES_PING_CURRENT_THRESHOLD:
            try:
                u = User.objects.get(id=row["user"])
            except Exception:
                print(f"could not find user: {row['user']}")
                continue
            title = "Taxes are due!"
            message = MININGTAXES_PING_CURRENT_MSG.format(row["balance"])
            notify(user=u, title=title, message=message, level="INFO")


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def apply_interest(self):
    settings = Settings.load()
    user2taxes = calctaxes()

    for u in user2taxes.keys():
        if user2taxes[u][0] <= 0.01:
            continue
        interest = round(user2taxes[u][0] * settings.interest_rate / 100.0, 2)
        if interest > MININGTAXES_PING_THRESHOLD:
            user2taxes[u][2].give_credit(-1.0 * interest, "interest")
            title = "Taxes are overdue!"
            message = MININGTAXES_PING_INTEREST_APPLIED.format(interest)
            notify(user=u, title=title, message=message, level="WARN")


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def auto_add_chars(self):
    from django.db import transaction
    from esi.models import Token

    scopes = Character.get_esi_scopes()
    tracked_corps = set()

    for achar in AdminCharacter.objects.all():
        tracked_corps.add(achar.eve_character.corporation_id)

    for char in EveCharacter.objects.all():
        # check if in plugin already
        try:
            inplug = Character.objects.get(eve_character=char)
            inplug = True
        except Character.DoesNotExist:
            inplug = False
            pass
        if inplug:
            continue
        # check if in tracked corp
        if char.corporation_id not in tracked_corps:
            continue
        # check if has token for esi scope
        token = Token.get_token(char.character_id, scopes)
        if not token:
            continue
        # check if orphaned and find user
        try:
            u = char.character_ownership.user.profile
        except EveCharacter.userprofile.RelatedObjectDoesNotExist:
            continue

        # check to see if MemberAudit is installed and if the character has entries in the mining ledger.
        detectedLedger = None
        try:
            from memberaudit.models import Character as maCharacter

            machar = maCharacter.objects.get(eve_character=char)
            num_ledger = len(machar.mining_ledger.all())
            detectedLedger = False
            if num_ledger > 0:
                detectedLedger = True
        except Exception:
            pass

        if detectedLedger is not None and not detectedLedger:
            continue

        logger.info(f"Need to add {char} to miningtaxes, user: {u}")
        with transaction.atomic():
            mcharacter, _ = Character.objects.update_or_create(eve_character=char)
        update_character(character_pk=mcharacter.pk)


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def update_daily(self):
    logger.info("Beginning price update")
    update_all_prices()

    logger.info("Beginning admin character updates")
    characters = AdminCharacter.objects.all()
    for character in characters:
        update_admin_character(character_pk=character.id, celery=True)

    logger.info("Running character update in parallel")
    chartasks = []
    characters = Character.objects.all()
    for character in characters:
        chartasks.append(update_character.s(character_pk=character.id, celery=True))

    chord(chartasks)(precalcs.s())


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def precalcs(self, output):
    perc = round(sum(output) / len(output) * 100, 2)
    logger.info(f"Starting Precalc: {perc}% update success")
    logger.info("Adding Corp Moon Taxes")
    add_corp_moon_taxes()
    logger.info("Linking Tax Payments")
    add_tax_credits()
    logger.info("Running each character's precalc")
    characters = Character.objects.all()
    # precalc all characters
    for character in characters:
        character.precalc_all()

    logger.info("Running Stats Precalc")
    s = Stats.load()
    s.precalc_all()
    logger.info("Finished precalc, updates complete")


def valid_janice_api_key():
    c = requests.get(
        "https://janice.e-351.com/api/rest/v2/markets",
        headers={
            "Content-Type": "text/plain",
            "X-ApiKey": MININGTAXES_PRICE_JANICE_API_KEY,
            "accept": "application/json",
        },
    ).json()

    if "status" in c:
        logger.debug("Janice API status: %s" % c)
        return False
    else:
        return True


def get_bulk_prices(type_ids):
    r = None
    if MININGTAXES_PRICE_METHOD == "Fuzzwork":
        r = requests.get(
            "https://market.fuzzwork.co.uk/aggregates/",
            params={
                "types": ",".join([str(x) for x in type_ids]),
                "station": MININGTAXES_PRICE_SOURCE_ID,
            },
        ).json()
    elif MININGTAXES_PRICE_METHOD == "Janice":
        r = requests.post(
            "https://janice.e-351.com/api/rest/v2/pricer?market=2",
            data="\n".join([str(x) for x in type_ids]),
            headers={
                "Content-Type": "text/plain",
                "X-ApiKey": MININGTAXES_PRICE_JANICE_API_KEY,
                "accept": "application/json",
            },
        ).json()

        # Make Janice data look like Fuzzworks
        output = {}
        for item in r:
            output[str(item["itemType"]["eid"])] = {
                "buy": {
                    "max": str(
                        item[MININGTAXES_PRICE_JANICE_TIMING][
                            MININGTAXES_PRICE_JANICE_BUY
                        ]
                    )
                },
                "sell": {
                    "min": str(
                        item[MININGTAXES_PRICE_JANICE_TIMING][
                            MININGTAXES_PRICE_JANICE_SELL
                        ]
                    )
                },
            }
        r = output
    else:
        raise f"Unknown pricing method: {MININGTAXES_PRICE_METHOD}"
    return r


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def update_all_prices(self, force=[]):
    type_ids = []
    market_data = {}
    api_up = True
    now = timezone.now()

    # Get all type ids by known groups
    prices = []
    added = set()

    for tid in force:
        if tid in (90665,):  # Patch to ignore bugged dev item for new installs
            continue
        e = ItemType.objects.get(id=tid)
        OrePrices.objects.create(eve_type=e, buy=0, sell=0, updated=now)
        added.add(tid)
        prices.append(e)

    for grp in PriceGroups().groups:
        g = ItemType.objects.filter(published=1, group_id=grp)
        for it in g:
            if it.id in added:
                continue
            added.add(it.id)
            prices.append(it)

    for o in OrePrices.objects.all():
        if o.eve_type_id in added:
            continue
        added.add(o.eve_type_id)
        prices.append(o.eve_type)

    # Update EveUniverse objects
    matset = set()
    for item in prices:
        if item.id in (90665,):  # Patch to ignore bugged dev item
            continue
        materials = ItemTypeMaterials.objects.filter(item_type_id=item.id)
        for mat in materials:
            mat = mat.material_item_type
            matset.add(mat.id)

    if MININGTAXES_PRICE_METHOD == "Fuzzwork":
        logger.debug("Using Fuzzwork")
        logger.debug(
            "Price setup starting for %s items from Fuzzworks API from station id %s (%s), this may take up to 30 seconds..."
            % (
                len(prices),
                MININGTAXES_PRICE_SOURCE_ID,
                MININGTAXES_PRICE_SOURCE_NAME,
            )
        )
    elif MININGTAXES_PRICE_METHOD == "Janice":
        logger.debug("Using Janice")
        if valid_janice_api_key():
            logger.debug(
                "Price setup starting for %s items from Janice API for Jita 4-4, this may take up to 30 seconds..."
                % (len(prices),)
            )
        else:
            logger.debug(
                "Price setup failed for Janice, invalid API key! Provide a working key or change price source to Fuzzwork"
            )
            api_up = False
    else:
        logger.error(
            "Unknown pricing method: '%s', skipping" % MININGTAXES_PRICE_METHOD
        )
        return

    if api_up:
        # Build suitable bulks to fetch prices from API
        for item in prices:
            type_ids.append(item.id)

            if len(type_ids) == 1000:
                market_data.update(get_bulk_prices(type_ids))
                type_ids.clear()

        # Get leftover data from the bulk
        if len(type_ids) > 0:
            market_data.update(get_bulk_prices(type_ids))

        logger.debug("Market data fetched, starting database update...")
        existing = OrePrices.objects.all()
        toupdate = []
        tocreate = []
        for price in prices:
            if not str(price.id) in market_data:
                logger.debug(f"Missing data on {price}")
                continue
            if price.id in matset:
                continue
            buy = int(float(market_data[str(price.id)]["buy"]["max"]))
            sell = int(float(market_data[str(price.id)]["sell"]["min"]))

            found = None
            for e in existing:
                if price.id == e.eve_type.id:
                    found = e
                    break
            if found is not None:
                found.buy = buy
                found.sell = sell
                found.updated = now
                toupdate.append(found)
            else:
                tocreate.append(
                    OrePrices(eve_type_id=price.id, buy=buy, sell=sell, updated=now)
                )

        # Handling refined material prices
        type_ids = list(matset)
        logger.debug(f"Materials price updating: {len(type_ids)}")
        market_data = {}
        market_data.update(get_bulk_prices(type_ids))
        for mat in matset:
            if not str(mat) in market_data:
                logger.debug(f"Missing data on {mat}")
                continue
            buy = int(float(market_data[str(mat)]["buy"]["max"]))
            sell = int(float(market_data[str(mat)]["sell"]["min"]))
            now = timezone.now()

            found = None
            for e in existing:
                if mat == e.eve_type.id:
                    found = e
                    break
            if found is not None:
                found.buy = buy
                found.sell = sell
                found.updated = now
                toupdate.append(found)
            else:
                tocreate.append(
                    OrePrices(eve_type_id=mat, buy=buy, sell=sell, updated=now)
                )

        logger.debug("Objects to be created: %d" % len(tocreate))
        logger.debug("Objects to be updated: %d" % len(toupdate))
        try:
            OrePrices.objects.bulk_create(tocreate)
            OrePrices.objects.bulk_update(toupdate, ["buy", "sell", "updated"])
            logger.debug("All prices succesfully updated")
        except Error as e:
            logger.error("Error updating prices: %s" % e)

        existing = OrePrices.objects.all()
        for e in existing:
            e.calc_prices()
    else:
        logger.error("Price source API is not up! Prices not updated.")


@shared_task(**{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def update_admin_character(
    self, character_pk: int, force_update: bool = False, celery=False
) -> bool:
    """Start respective update tasks for all stale sections of a character

    Args:
    - character_pk: PL of character to update
    - force_update: When set to True will always update regardless of stale status

    Returns:
    - True when update was conducted
    - False when no updated was needed
    """
    character = AdminCharacter.objects.get(pk=character_pk)
    if character.is_orphan:
        logger.info("%s: Skipping update for orphaned character", character)
        return False
    needs_update = force_update
    needs_update |= character.is_ledger_stale()

    if not needs_update:
        logger.info("%s: No update required", character)
        return False

    logger.info(
        "%s: Starting %s character update", character, "forced" if force_update else ""
    )

    character.update_all()
    if not celery and MININGTAXES_TAX_ONLY_CORP_MOONS:
        add_corp_moon_taxes()


def add_tax_credits():
    settings = Settings.load()
    characters = AdminCharacter.objects.all()
    phrase = settings.phrase.lower().strip()
    for character in characters:
        entries = character.corp_ledger.all()
        for entry in entries:
            if phrase != "" and phrase not in entry.reason.lower():
                continue
            try:
                payee = get_object_or_404(
                    Character,
                    eve_character_id=EveCharacter.objects.get(
                        character_id=entry.taxed_id
                    ).pk,
                )
            except Character.DoesNotExist:
                payee = get_user(entry.taxed_id)
                if payee is None:
                    continue
                pass
            except Http404:
                continue
            except EveCharacter.DoesNotExist:
                continue
            payee.tax_credits.update_or_create(
                date=entry.date, credit=entry.amount, defaults={"credit_type": "paid"}
            )


def add_tax_credits_by_char(character):
    settings = Settings.load()
    entries = AdminMiningCorpLedgerEntry.objects.filter(
        taxed_id=character.eve_character.character_id
    )
    for entry in entries:
        if settings.phrase != "" and settings.phrase not in entry.reason:
            continue
        character.tax_credits.update_or_create(
            date=entry.date, credit=entry.amount, defaults={"credit_type": "paid"}
        )


def add_corp_moon_taxes():
    characters = Character.objects.all()
    for character in characters:
        add_corp_moon_taxes_by_char(character)


def add_corp_moon_taxes_by_char(character):
    entries = AdminMiningObsLog.objects.filter(
        miner_id=character.eve_character.character_id
    )
    consolidate = {}
    for entry in entries:
        k = f"{entry.date}\t{entry.eve_solar_system_id}\t{entry.eve_type_id}"
        if k not in consolidate:
            consolidate[k] = 0
        consolidate[k] += entry.quantity

    for k in consolidate.keys():
        edate, esys, etype = k.split("\t")
        equantity = consolidate[k]
        try:
            row = character.mining_ledger.get(
                date=edate,
                eve_solar_system_id=esys,
                eve_type_id=etype,
            )
            if row.quantity != equantity:
                row.quantity = equantity
                row.save()
                row.calc_prices(corpmoon=True)
        except CharacterMiningLedgerEntry.DoesNotExist:
            row = character.mining_ledger.create(
                date=edate,
                eve_solar_system_id=esys,
                eve_type_id=etype,
                quantity=equantity,
            )
            row.calc_prices(corpmoon=True)


@shared_task(ignore_result=False, **{**TASK_DEFAULT_KWARGS, **{"bind": True}})
def update_character(
    self, character_pk: int, force_update: bool = False, celery=False
) -> bool:
    """Start respective update tasks for all stale sections of a character

    Args:
    - character_pk: PL of character to update
    - force_update: When set to True will always update regardless of stale status

    Returns:
    - True when update was conducted
    - False when no updated was needed
    """
    character = Character.objects.get(pk=character_pk)
    if character.is_orphan:
        logger.info("%s: Skipping update for orphaned character", character)
        return False
    needs_update = force_update
    needs_update |= character.is_ledger_stale()

    if not needs_update:
        logger.info("%s: No update required", character)
        return False

    try:
        logger.info(
            "%s: Starting %s character update",
            character,
            "forced" if force_update else "",
        )
        character.update_mining_ledger()
        add_tax_credits_by_char(character)
        if not celery and MININGTAXES_TAX_ONLY_CORP_MOONS:
            add_corp_moon_taxes_by_char(character)
    except TokenError:
        p = Permission.objects.get(
            content_type__app_label=Character._meta.app_label, codename="admin_access"
        )
        logger.warn("Missing ESI Token for %s", character)
        title = f"Missing ESI Token for {character}"
        message = f"MiningTaxes could not fetch the mining ledger for {character}."
        for u in users_with_permission(p):
            notify(user=u, title=title, message=message, level="CRITICAL")
        pass
    return False
