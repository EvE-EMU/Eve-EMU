import datetime
from decimal import Decimal
from random import randint
from typing import Literal

from celery import shared_task
from eve_sde.models import ItemType, Region, SolarSystem

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F, Q, Sum

from allianceauth.eveonline.models import EveCharacter, EveCorporationInfo
from allianceauth.services.hooks import get_extension_logger
from esi.exceptions import (
    ESIBucketLimitException, ESIErrorLimitException, HTTPNotModified,
)
from esi.models import Token

from marketmanager.app_settings import (
    MARKETMANAGER_CLEANUP_DAYS_ORDER, MARKETMANAGER_TASK_JITTER,
    MARKETMANAGER_TASK_PRIORITY_BACKGROUND,
    MARKETMANAGER_TASK_PRIORITY_MARGIN_CONFIGS,
    MARKETMANAGER_TASK_PRIORITY_ORDERS,
    MARKETMANAGER_TASK_PRIORITY_PRICE_CONFIGS,
    MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
    MARKETMANAGER_TASK_PRIORITY_SUPPLY_CONFIGS,
    MARKETMANAGER_TYPESTATISTICS_MINIMUM_ORDER_COUNT,
    MARKETMANAGER_WEBHOOK_COLOUR_ERROR, MARKETMANAGER_WEBHOOK_COLOUR_SUCCESS,
    MARKETMANAGER_WEBHOOK_COLOUR_WARNING, discord_bot_active, fittings_active,
)
from marketmanager.models import (
    ManagedSupplyConfig, MarginConfig, Order, PriceConfig, PublicConfig,
    StatisticsConfig, Structure, SupplyConfig, TypeStatistics,
)
from marketmanager.providers import (
    get_characters_character_id_orders, get_corporations_corporation_id_orders,
    get_corporations_corporation_id_structures,
    get_markets_region_id_orders_by_typeid_paged,
    get_markets_region_id_orders_paged, get_markets_structures_structure_id,
    get_universe_structures, get_universe_structures_structure_id,
)
from marketmanager.task_helpers import (
    calculate_comparator_price, create_embed_margin, create_embed_price,
    create_embed_supply, fifth_percentile, filter_orders_by_location,
    get_corp_token, get_matching_privateconfig_token, get_random_market_token,
    is_existing_order, location_resolver_to_solar_system, median,
    weighted_average,
)

if fittings_active():
    from marketmanager.fittings import (
        update_managed_supply_config_fittings_fit,
    )

if discord_bot_active():
    from aadiscordbot.tasks import send_message

logger = get_extension_logger(__name__)


@shared_task
def fetch_public_market_orders() -> None:
    """Fetch&Save Public Market Orders for configured regions
    bulk calls fetch_markets_region_id_orders(region_id: int)"""
    logger.debug("fetch_public_market_orders(), Fetching configured regions")
    for region in PublicConfig.get_solo().fetch_regions.all():
        logger.debug(f"fetch_public_market_orders(), Queuing up celery task for region {region.id}")
        fetch_markets_region_id_orders.apply_async(  # pyright: ignore[reportCallIssue, reportFunctionMemberAccess]
            args=[region.id, 'buy'],
            priority=MARKETMANAGER_TASK_PRIORITY_ORDERS,
            countdown=randint(1, MARKETMANAGER_TASK_JITTER))
        fetch_markets_region_id_orders.apply_async(  # pyright: ignore[reportCallIssue, reportFunctionMemberAccess]
            args=[region.id, 'sell'],
            priority=MARKETMANAGER_TASK_PRIORITY_ORDERS,
            countdown=randint(1, MARKETMANAGER_TASK_JITTER))


@shared_task(bind=True)
def fetch_markets_region_id_orders(self, region_id: int, order_type: Literal['buy', 'sell', 'all'] = 'all', type_id: int | None = None) -> None:
    logger.debug(f"fetch_markets_region_id_orders({region_id})")
    order_region = Region.objects.get(id=region_id)
    if order_type == 'buy':
        current_orders = Order.objects.filter(region=order_region, is_buy_order=True,)
    elif order_type == 'sell':
        current_orders = Order.objects.filter(region=order_region, is_buy_order=False,)
    else:
        current_orders = Order.objects.filter(region=order_region)

    current_page = 1
    total_pages = 1
    while current_page <= total_pages:
        new_orders = []
        updated_orders = []
        if type_id is not None:
            try:
                order_page, order_page_headers = get_markets_region_id_orders_by_typeid_paged(region_id, current_page, order_type, type_id=type_id)
            except (ESIErrorLimitException, ESIBucketLimitException) as e:
                raise self.retry(exc=e, countdown=e.reset + 1 if e.reset is not None else 61)
            except HTTPNotModified:
                return
        else:
            order_page, order_page_headers = get_markets_region_id_orders_paged(region_id, current_page, order_type)
        total_pages = int(order_page_headers.headers['X-Pages'])
        current_page += 1
        for order in order_page:
            existing_order = is_existing_order(order, current_orders)
            if existing_order is not False:
                if existing_order.price != order.price or existing_order.volume_remain != order.volume_remain or existing_order.issued != order.issued:
                    existing_order.price = order.price
                    existing_order.volume_remain = order.volume_remain
                    existing_order.issued = order.issued
                    updated_orders.append(existing_order)
                else:
                    # It is an existing order, but hasn't changed, so nothing
                    pass
            else:
                new_order = Order(order_id=order.order_id)
                new_order.item_type = ItemType.objects.get(id=order.type_id)
                new_order.duration = order.duration
                new_order.is_buy_order = order.is_buy_order
                new_order.issued = order.issued
                new_order.location_id = order.location_id
                new_order.min_volume = order.min_volume
                new_order.price = order.price
                new_order.range = order.range
                new_order.solar_system = SolarSystem.objects.get(id=order.system_id)
                new_order.region = order_region
                new_order.volume_remain = order.volume_remain
                new_orders.append(new_order)
        try:
            Order.objects.bulk_create(new_orders, batch_size=500)
            Order.objects.bulk_update(updated_orders, batch_size=500, fields=['price', 'volume_remain', 'issued'])
        except Exception as e:
            logger.exception(e)


@shared_task(bind=True)
def fetch_characters_character_id_orders(self, character_id: int, order_type: Literal['buy', 'sell', 'all'] = 'all') -> None:
    """Fetch&Save a single Characters Market Orders
    bulk called by fetch_all_character_orders()

    Parameters
    ----------
    corporation_id: int
        Should match a valid Character ID"""
    logger.debug(f"fetch_characters_character_id_orders({character_id})")
    try:
        orders = get_characters_character_id_orders(character_id)
    except (ESIErrorLimitException, ESIBucketLimitException) as e:
        raise self.retry(exc=e, countdown=e.reset + 1 if e.reset is not None else 61)
    except HTTPNotModified:
        return
    for order in orders:
        try:
            order_eve_character = EveCharacter.objects.get(character_id=character_id)
        except ObjectDoesNotExist:
            EveCharacter.objects.create_character(character_id)
            order_eve_character = EveCharacter.objects.get(
                character_id=character_id
            )
        # Need to manually resolve this, as this endpoint is different and doesn't include the solar system
        order_solar_system = location_resolver_to_solar_system(order.location_id)

        # Need to handle None's here, as its an optional field in this endpoint
        # for some reason? #CCP\
        if order.is_buy_order is not True:
            order_is_buy_order = False
        else:
            order_is_buy_order = True

        try:
            Order.objects.update_or_create(
                order_id=order.order_id,
                defaults={
                    'item_type': ItemType.objects.get(id=order.type_id),
                    'duration': order.duration,
                    'is_buy_order': order_is_buy_order,
                    'is_corporation': order.is_corporation,
                    'issued': order.issued,
                    'issued_by_character': order_eve_character,
                    'location_id': order.location_id,
                    'region': Region.objects.get(id=order.region_id),
                    'min_volume': order.min_volume,
                    'price': order.price,
                    'range': order.range,
                    'volume_remain': order.volume_remain,
                    'solar_system': order_solar_system,
                }
            )
        except Exception as e:
            logger.exception(e)
        logger.debug(
            f"fetch_characters_character_id_orders({character_id}): Saved Order {ItemType.objects.get(id=order.type_id).name}")


@shared_task()
def fetch_all_character_orders() -> None:
    """Fetch&Save every Characters Market Orders
    bulk calls fetch_characters_character_id_orders(character_id)"""
    logger.debug("fetch_all_character_orders()")
    character_ids = Token.objects.values_list('character_id').require_scopes(["esi-markets.read_character_orders.v1"])
    unique_character_ids = list(dict.fromkeys(character_ids))
    for character_id in unique_character_ids:
        logger.debug(f"fetch_all_character_orders(), Queuing up celery task for character {character_id}")
        fetch_characters_character_id_orders.apply_async(
            args=[character_id[0]],
            priority=MARKETMANAGER_TASK_PRIORITY_ORDERS,
            countdown=randint(1, MARKETMANAGER_TASK_JITTER))   # pyright: ignore[reportCallIssue]


@shared_task(bind=True)
def fetch_corporations_corporation_id_orders(self, corporation_id: int) -> None:
    """Fetch&Save a Corporations Market Orders
    Is Bulk-Called by fetch_all_corporation_orders()

    Parameters
    ----------
    corporation_id: int
        Should match a valid Corporation ID"""
    logger.debug(f"fetch_corporations_corporation_id_orders({corporation_id})")
    scopes = ["esi-markets.read_corporation_orders.v1"]
    req_roles = ["Accountant", "Trader"]

    token = get_corp_token(corporation_id, scopes, req_roles)
    if token is False:
        logger.error(f"No Token for Corporation {corporation_id}")
        return
    order_eve_corporation = EveCorporationInfo.objects.get(corporation_id=corporation_id)

    try:
        orders = get_corporations_corporation_id_orders(corporation_id, token)
    except (ESIErrorLimitException, ESIBucketLimitException) as e:
        raise self.retry(exc=e, countdown=e.reset + 1 if e.reset is not None else 61)
    except HTTPNotModified:
        return

    for order in orders:
        try:
            order_eve_character = EveCharacter.objects.get(character_id=order.issued_by)
        except ObjectDoesNotExist:
            EveCharacter.objects.create_character(order.issued_by)
            order_eve_character = EveCharacter.objects.get(character_id=order.issued_by)

        # Need to manually resolve this, as this endpoint is different and doesn't include the solar system
        order_solar_system = location_resolver_to_solar_system(order.location_id)
        # Need to handle None's here, as its an optional field in this endpoint

        # for some reason? #CCP\
        if order.is_buy_order is not True:
            order_is_buy_order = False
        else:
            order_is_buy_order = True
        try:
            Order.objects.update_or_create(
                order_id=order.order_id,
                defaults={
                    'item_type': ItemType.objects.get(id=order.type_id),
                    'duration': order.duration,
                    'is_buy_order': order_is_buy_order,
                    'is_corporation': True,
                    'issued': order.issued,
                    'issued_by_character': order_eve_character,
                    'issued_by_corporation': order_eve_corporation,
                    'wallet_division': order.wallet_division,
                    'location_id': order.location_id,
                    'region': Region.objects.get(id=order.region_id),
                    'min_volume': order.min_volume,
                    'price': order.price,
                    'range': order.range,
                    'volume_remain': order.volume_remain,
                    'solar_system': order_solar_system
                }
            )
        except Exception as e:
            logger.exception(e)


@shared_task()
def fetch_all_corporation_orders() -> None:
    """Fetch&Save every Corporations Market Orders
    bulk calls fetch_corporations_corporation_id_orders(corporation_id)"""
    logger.debug("fetch_all_corporation_orders()")
    for corporation in EveCorporationInfo.objects.filter(corporation_id__gt=1999999):  # Exclude NPC Corps
        logger.debug(
            f"fetch_all_corporation_orders(), Queuing up celery task for corporation {corporation.corporation_id}")
        fetch_corporations_corporation_id_orders.apply_async(
            args=[corporation.corporation_id],
            priority=MARKETMANAGER_TASK_PRIORITY_ORDERS,
            countdown=randint(1, MARKETMANAGER_TASK_JITTER))  # pyright: ignore[reportCallIssue]


@shared_task(bind=True)
def fetch_public_structures(self) -> None:
    logger.debug("fetch_public_structures()")
    try:
        structures = get_universe_structures(filter="market")
    except (ESIErrorLimitException, ESIBucketLimitException) as e:
        raise self.retry(exc=e, countdown=e.reset + 1 if e.reset is not None else 61)
    except HTTPNotModified:
        return
    for structure_id in structures:
        logger.debug(f"fetch_public_structures(), Queuing up celery task for structure {structure_id}")
        fetch_universe_structures_structure_id.apply_async(
            args=[structure_id],
            priority=MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
            countdown=randint(1, MARKETMANAGER_TASK_JITTER))  # pyright: ignore[reportCallIssue]


@shared_task()
def update_private_structures() -> None:
    logger.debug("update_private_structures()")
    for structure in Structure.objects.all():
        fetch_universe_structures_structure_id.apply_async(
            args=[structure.structure_id, False],
            priority=MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
            countdown=randint(1, MARKETMANAGER_TASK_JITTER))  # pyright: ignore[reportCallIssue]


@shared_task(bind=True)
def fetch_universe_structures_structure_id(self, structure_id: int, public=True) -> None:
    logger.debug(f"fetch_universe_structures_structure_id({structure_id})")
    if public is True:
        token = get_random_market_token()
    else:
        token = get_matching_privateconfig_token(structure_id)

    if token is False:
        logger.error(
            f"No Public or Private token (Public={public}) for {structure_id}")
        return

    try:
        structure = get_universe_structures_structure_id(structure_id, token)
    except (ESIErrorLimitException, ESIBucketLimitException) as e:
        raise self.retry(exc=e, countdown=e.reset + 1 if e.reset is not None else 61)
    except HTTPNotModified:
        return

    try:
        Structure.objects.update_or_create(
            structure_id=structure_id,
            defaults={
                'name': structure.name,
                'owner_id': structure.owner_id,
                'solar_system': SolarSystem.objects.get(id=structure.solar_system_id),
                'item_type': ItemType.objects.get(id=structure.type_id)
            }
        )
    except Exception as e:
        logger.exception(e)


@shared_task()
def fetch_all_structure_orders() -> None:
    logger.debug("fetch_all_structure_orders()")
    for structure in Structure.objects.all():
        logger.debug(f"fetch_all_structure_orders(), Queuing up celery task for structure {structure.structure_id}")
        fetch_markets_structures_structure_id.apply_async(
            args=[structure.structure_id],
            priority=MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
            countdown=randint(1, MARKETMANAGER_TASK_JITTER))  # pyright: ignore[reportCallIssue]


@shared_task(bind=True)
def fetch_markets_structures_structure_id(self, structure_id: int) -> None:
    logger.debug(f"fetch_markets_structures_structure_id({structure_id})")

    token = get_matching_privateconfig_token(structure_id)

    if token is False:
        logger.error(f"No Token PrivateConfig for structure {structure_id}")
        return

    try:
        orders = get_markets_structures_structure_id(structure_id, token)
    except (ESIErrorLimitException, ESIBucketLimitException) as e:
        raise self.retry(exc=e, countdown=e.reset + 1 if e.reset is not None else 61)
    except HTTPNotModified:
        return

    for order in orders:

        try:
            Order.objects.update_or_create(
                order_id=order.order_id,
                defaults={
                    'item_type': ItemType.objects.get(id=order.type_id),
                    'duration': order.duration,
                    'is_buy_order': order.is_buy_order,
                    'issued': order.issued,
                    'location_id': order.location_id,
                    'solar_system': Structure.objects.get(structure_id=structure_id).solar_system,
                    'region': Structure.objects.get(structure_id=structure_id).solar_system.constellation.region,
                    'min_volume': order.min_volume,
                    'price': order.price,
                    'range': order.range,
                    'volume_remain': order.volume_remain,
                }
            )
        except Exception as e:
            logger.exception(e)


@shared_task()
def fetch_all_corporations_structures() -> None:
    logger.debug("fetch_all_corporations_structures()")
    for corporation in EveCorporationInfo.objects.all():
        logger.debug(
            f"fetch_all_corporations_structures(), Queuing up celery task for corporation {corporation.corporation_id}")
        fetch_corporations_corporation_id_structures.apply_async(
            args=[corporation.corporation_id],
            priority=MARKETMANAGER_TASK_PRIORITY_STRUCTURES,
            countdown=randint(1, MARKETMANAGER_TASK_JITTER))  # pyright: ignore[reportCallIssue]


@shared_task(bind=True)
def fetch_corporations_corporation_id_structures(self, corporation_id: int) -> None:
    logger.debug(f"fetch_corporations_corporation_id_structures({corporation_id})")
    if corporation_id < 2000000:
        logger.error(f"Corporation ID {corporation_id} is an NPC Corporation, skipping.")
        return
    scopes = ["esi-corporations.read_structures.v1"]
    req_roles = ["Station_Manager"]

    token = get_corp_token(corporation_id, scopes, req_roles)
    if token is False:
        logger.error(f"No Token for Corporation {corporation_id}")
        return

    try:
        structures = get_corporations_corporation_id_structures(corporation_id, token)
    except (ESIErrorLimitException, ESIBucketLimitException) as e:
        raise self.retry(exc=e, countdown=e.reset + 1 if e.reset is not None else 61)
    except HTTPNotModified:
        return

    for structure in structures:
        for service in structure.services if structure.services else []:
            if service.name == "market":
                try:
                    Structure.objects.update_or_create(
                        structure_id=structure.structure_id,
                        defaults={
                            'name': structure.name,
                            'owner_id': structure.corporation_id,
                            'solar_system': SolarSystem.objects.get(id=structure.system_id),
                            'item_type': ItemType.objects.get(id=structure.type_id),
                            'updated_at': datetime.datetime.now()
                        }
                    )
                except Exception as e:
                    logger.exception(e)


@shared_task()
def run_all_watch_configs() -> None:
    for config in SupplyConfig.objects.all():
        run_supply_config.apply_async(
            args=[config.pk], priority=MARKETMANAGER_TASK_PRIORITY_SUPPLY_CONFIGS)  # pyright: ignore[reportCallIssue]
    for config in PriceConfig.objects.all():
        run_price_config.apply_async(
            args=[config.pk], priority=MARKETMANAGER_TASK_PRIORITY_PRICE_CONFIGS)  # pyright: ignore[reportCallIssue]
    for config in MarginConfig.objects.all():
        run_margin_config.apply_async(
            args=[config.pk], priority=MARKETMANAGER_TASK_PRIORITY_MARGIN_CONFIGS)  # pyright: ignore[reportCallIssue]


@shared_task()
def run_supply_config(id: int) -> None:
    config = SupplyConfig.objects.get(id=id)
    matching_orders = Order.objects.filter(
        item_type=config.item_type,
        is_buy_order=config.buy_order)
    matching_orders_location = filter_orders_by_location(matching_orders, config)
    comparator_price = calculate_comparator_price(config)

    if config.jita_compare_percent != 0:
        try:
            type_statistics = TypeStatistics.objects.get(
                item_type=config.item_type,
                region=Region.objects.get(id=10000002))
            if config.buy_order is True:
                comparator_price = type_statistics.buy_weighted_average * (config.jita_compare_percent / 100)
            if config.buy_order is False:
                comparator_price = type_statistics.sell_weighted_average * (config.jita_compare_percent / 100)
        except ObjectDoesNotExist:
            comparator_price = 0

    if comparator_price != 0 and config.buy_order is True:
        matching_orders_location_price = matching_orders_location.filter(price__gte=comparator_price)
    elif comparator_price != 0 and config.buy_order is False:
        matching_orders_location_price = matching_orders_location.filter(price__lte=comparator_price)
    else:
        matching_orders_location_price = matching_orders_location

    matched_volume = matching_orders_location_price.aggregate(
        aggregate_volume=Sum('volume_remain'))["aggregate_volume"]
    matched_cumulative_price = matching_orders_location_price.aggregate(
        aggregate_price=Sum(F('volume_remain') * F("price")))['aggregate_price']
    if not isinstance(matched_volume, int):
        matched_volume = 0
    if matching_orders_location_price.count() > 0:
        if matched_volume >= config.volume:
            embed = create_embed_supply(
                config=config,
                matched_volume=matched_volume,
                description="The following Supply Check reported no Errors",
                calculated_price=comparator_price,
                colour=MARKETMANAGER_WEBHOOK_COLOUR_SUCCESS)
            embed.insert_field_at(
                index=3,
                name="Market Price (w/Avg)",
                value=f"{matched_cumulative_price / matched_volume:,.2f} ISK"
            )
            webhooks = config.debug_webhooks.all()
            for webhook in webhooks:
                if webhook.enabled:
                    webhook.send_embed(embed)
            channels = config.debug_channels.all()
            for channel in channels:
                if discord_bot_active():
                    send_message(channel_id=channel.id, embed=embed)

        else:
            embed = create_embed_supply(
                config=config,
                matched_volume=matched_volume,
                description="The following Supply Check failed to return enough Volume",
                calculated_price=comparator_price,
                colour=MARKETMANAGER_WEBHOOK_COLOUR_WARNING)
            embed.insert_field_at(
                index=3,
                name="Market Price (w/Avg)",
                value=f"{matched_cumulative_price / matched_volume:,.2f} ISK"
            )
            webhooks = config.webhooks.all()
            for webhook in webhooks:
                if webhook.enabled:
                    webhook.send_embed(embed)
            channels = config.channels.all()
            for channel in channels:
                if discord_bot_active():
                    send_message(channel_id=channel.id, embed=embed)
    else:
        embed = create_embed_supply(
            config=config,
            matched_volume=matched_volume,
            description="The following Supply Check returned zero volume, This item may be out of stock or Market Manager may be incorrectly configured",
            calculated_price=comparator_price,
            colour=MARKETMANAGER_WEBHOOK_COLOUR_ERROR)
        webhooks = config.webhooks.all()
        for webhook in webhooks:
            if webhook.enabled:
                webhook.send_embed(embed)
        channels = config.channels.all()
        for channel in channels:
            if discord_bot_active():
                send_message(channel_id=channel.id, embed=embed)

    config.last_result_volume = matched_volume
    config.last_run = datetime.datetime.now()
    config.save()


@shared_task()
def run_price_config(id: int) -> None:
    config = PriceConfig.objects.get(id=id)
    orders = Order.objects.filter(is_buy_order=config.buy_order)
    orders_location = filter_orders_by_location(orders, config)
    orders_location_type = orders_location.filter(
        Q(item_type__in=config.item_type.all()) | Q(item_type__item_group__in=config.item_group.all())
        | Q(item_type__item_market_group__in=config.item_market_group.all())
        | Q(item_type__item_market_group__parent_market_group__in=config.item_market_group.all())
        | Q(item_type__item_market_group__parent_market_group__parent_market_group__in=config.item_market_group.all())
        | Q(item_type__item_market_group__parent_market_group__parent_market_group__parent_market_group__in=config.item_market_group.all())
        | Q(item_type__item_market_group__parent_market_group__parent_market_group__parent_market_group__parent_market_group__in=config.item_market_group.all())
    )

    embed_description = ""

    for order in orders_location_type.order_by('item_type', '-price'):
        if len(embed_description) > 3800:
            embed = create_embed_price(
                config=config,
                description=embed_description,
            )
            webhooks = config.webhooks.all()
            for webhook in webhooks:
                if webhook.enabled:
                    webhook.send_embed(embed)
            channels = config.channels.all()
            for channel in channels:
                if discord_bot_active():
                    send_message(channel_id=channel.id, embed=embed)
            embed_description = ""
        else:
            try:
                if order.price > config.minimum or config.minimum == 0:
                    if config.scalp is True and order.price > TypeStatistics.objects.get(
                            item_type=order.item_type,
                            region=Region.objects.get(id=10000002)
                    ).sell_weighted_average * (config.jita_compare_percent / 100):
                        embed_description += f"{order.item_type} x {order.volume_remain} @ {order.price:,} ISK\n"
                    if config.scalp is False and order.price < TypeStatistics.objects.get(
                            item_type=order.item_type,
                            region=Region.objects.get(id=10000002)
                    ).sell_weighted_average * (config.jita_compare_percent / 100):
                        embed_description += f"{order.item_type} x {order.volume_remain} @ {order.price:,} ISK\n"
            except Exception as e:
                logger.exception(e)

    embed = create_embed_price(
        config=config,
        description=embed_description,
    )
    webhooks = config.webhooks.all()
    for webhook in webhooks:
        if webhook.enabled:
            webhook.send_embed(embed)
    channels = config.channels.all()
    for channel in channels:
        if discord_bot_active():
            send_message(channel_id=channel.id, embed=embed)
    config.last_run = datetime.datetime.now()
    config.save()


@shared_task()
def run_margin_config(id: int) -> None:
    config = MarginConfig.objects.get(id=id)

    item_types = config.item_type.all() | ItemType.objects.filter(item_group__in=config.item_group.all()) \
        | ItemType.objects.filter(item_market_group__in=config.item_market_group.all()) \
        | ItemType.objects.filter(item_market_group__parent_market_group__in=config.item_market_group.all()) \
        | ItemType.objects.filter(item_market_group__parent_market_group__parent_market_group__in=config.item_market_group.all()) \
        | ItemType.objects.filter(item_market_group__parent_market_group__parent_market_group__parent_market_group__in=config.item_market_group.all()) \
        | ItemType.objects.filter(item_market_group__parent_market_group__parent_market_group__parent_market_group__parent_market_group__in=config.item_market_group.all())

    # I cant use the filter helper i made, that doesn't handle having two separate sets of regions
    # refactor this so i can? still need to handle buy and order anyway here, so maybe makes sense to still do it here
    if config.source_buy is True:
        if config.source_structure.count() > 0 or config.source_solar_system.count() > 0 or config.source_region.count() > 0 or config.source_station.count() > 0:
            source_orders = Order.objects.filter(
                Q(location_id__in=config.source_structure.all()) | Q(location_id__in=config.source_station.all()) | Q(solar_system__in=config.source_solar_system.all()) | Q(region__in=config.source_region.all()), is_buy_order=True).order_by('price')
    else:
        if config.source_structure.count() > 0 or config.source_solar_system.count() > 0 or config.source_region.count() > 0 or config.source_station.count() > 0:
            source_orders = Order.objects.filter(
                Q(location_id__in=config.source_structure.all()) | Q(location_id__in=config.source_station.all()) | Q(solar_system__in=config.source_solar_system.all()) | Q(region__in=config.source_region.all()), is_buy_order=False).order_by('-price')

    if config.destination_buy is True:
        if config.destination_structure.count() > 0 or config.destination_solar_system.count() > 0 or config.destination_region.count() > 0 or config.destination_station.count() > 0:
            destination_orders = Order.objects.filter(
                Q(location_id__in=config.destination_structure.all()) | Q(location_id__in=config.destination_station.all()) | Q(solar_system__in=config.destination_solar_system.all()) | Q(region__in=config.destination_region.all()), is_buy_order=True).order_by('price')
    else:
        if config.destination_structure.count() > 0 or config.destination_solar_system.count() > 0 or config.destination_region.count() > 0 or config.destination_station.count() > 0:
            destination_orders = Order.objects.filter(
                Q(location_id__in=config.destination_structure.all()) | Q(location_id__in=config.destination_station.all()) | Q(solar_system__in=config.destination_solar_system.all()) | Q(region__in=config.destination_region.all()), is_buy_order=False).order_by('-price')

    embed_description = ""

    for item_type in item_types:

        if len(embed_description) > 3800:
            embed = create_embed_margin(
                config=config,
                description=embed_description,
            )
            webhooks = config.webhooks.all()
            for webhook in webhooks:
                if webhook.enabled:
                    webhook.send_embed(embed)
            channels = config.channels.all()
            for channel in channels:
                if discord_bot_active():
                    send_message(channel_id=channel.id, embed=embed)
            embed_description = ""
        else:
            try:
                if (destination_orders.filter(item_type=item_type).last().price / (source_orders.filter(item_type=item_type).last().price + Decimal(item_type.volume * config.freight_cost))) * 100 - 100 > config.margin_percent:
                    embed_description += f"`{item_type}` @ {(destination_orders.filter(item_type=item_type).last().price / (source_orders.filter(item_type=item_type).last().price + Decimal(item_type.volume * config.freight_cost))) * 100 - 100:,.0f}%: {destination_orders.filter(item_type=item_type).last().price:,} ISK > {source_orders.filter(item_type=item_type).last().price + Decimal(item_type.volume * config.freight_cost):,} ISK\n"
            except AttributeError:
                # Item has no price, its not for sale in one or both locations :shrug:
                pass
            except Exception as e:
                logger.exception(e)

    embed = create_embed_margin(
        config=config,
        description=embed_description,
    )
    webhooks = config.webhooks.all()
    for webhook in webhooks:
        if webhook.enabled:
            webhook.send_embed(embed)
    channels = config.channels.all()
    for channel in channels:
        if discord_bot_active():
            send_message(channel_id=channel.id, embed=embed)
    config.last_run = datetime.datetime.now()
    config.save()


@shared_task()
def garbage_collection():
    # Orders
    # Generic Expiry Date Passed
    order_passed_expiry_date = datetime.datetime.now() - datetime.timedelta(days=90)
    orders_expired_by_generic_date = Order.objects.filter(
        issued__lt=order_passed_expiry_date)
    orders_expired_by_generic_date.delete()
    # Calculated Expiry Date Passed
    # Cant do this, property
    # orders_expired_by_calculated_date = Order.objects.filter(expiry__lt=datetime.datetime.now())
    # orders_expired_by_calculated_date.delete()
    # State = Expired or Cancelled
    orders_expired_by_state = Order.objects.filter(
        Q(state="Expired") | Q(state="Cancelled"))
    orders_expired_by_state.delete()
    # Stale
    order_stale_cleanup_date = datetime.datetime.now() - datetime.timedelta(days=MARKETMANAGER_CLEANUP_DAYS_ORDER)
    orders_stale = Order.objects.filter(updated_at__lt=order_stale_cleanup_date)
    orders_stale.delete()
    # Structures
    # Stale
    # structure_stale_cleanup_date = datetime.datetime.now(
    # ) - datetime.timedelta(days=MARKETMANAGER_CLEANUP_DAYS_STRUCTURE)
    # structures_stale = Structure.objects.filter(
    #     updated_at__lt=structure_stale_cleanup_date)
    # structures_stale.delete()


@shared_task()
def update_all_type_statistics() -> None:
    logger.debug("update_all_type_statistics()")
    for item_type in ItemType.objects.filter(item_market_group__isnull=False, published=1):
        if Order.objects.filter(item_type=item_type).count() >= MARKETMANAGER_TYPESTATISTICS_MINIMUM_ORDER_COUNT:
            calculate_type_statistics.apply_async(
                args=[item_type.id], priority=MARKETMANAGER_TASK_PRIORITY_BACKGROUND)  # pyright: ignore[reportCallIssue]
        else:
            TypeStatistics.objects.filter(item_type=item_type).delete()


@shared_task()
def calculate_type_statistics(type_id: int) -> None:
    item_type = ItemType.objects.get(id=type_id)
    try:
        logger.debug(f"calculate_type_statistics ItemType ({item_type.name}) Region (NEW EDEN)")
        TypeStatistics.objects.update_or_create(
            item_type=item_type,
            region=None,
            defaults={
                'buy_fifth_percentile': fifth_percentile(item_type=item_type, buy_order=True),
                'sell_fifth_percentile': fifth_percentile(item_type=item_type, buy_order=False),
                'buy_weighted_average': weighted_average(item_type=item_type, buy_order=True),
                'sell_weighted_average': weighted_average(item_type=item_type, buy_order=False),
                'buy_median': median(item_type=item_type, buy_order=True),
                'sell_median': median(item_type=item_type, buy_order=False),
            }
        )
    except Exception as e:
        logger.exception(e)

    for region in StatisticsConfig.get_solo().calculate_regions.all():
        logger.debug(f"calculate_type_statistics ItemType ({item_type.name}) Region ({region.name})")
        if Order.objects.filter(item_type=item_type, region=region).exists():
            try:
                TypeStatistics.objects.update_or_create(
                    item_type=item_type,
                    region=region,
                    defaults={
                        'buy_fifth_percentile': fifth_percentile(item_type=item_type, region=region, buy_order=True),
                        'sell_fifth_percentile': fifth_percentile(item_type=item_type, region=region, buy_order=False),
                        'buy_weighted_average': weighted_average(item_type=item_type, region=region, buy_order=True),
                        'sell_weighted_average': weighted_average(item_type=item_type, region=region, buy_order=False),
                        'buy_median': median(item_type=item_type, region=region, buy_order=True),
                        'sell_median': median(item_type=item_type, region=region, buy_order=False),
                    }
                )
            except Exception as e:
                logger.exception(e)
        else:  # In case we have old statistics, we'd want to wipe them for objects no longer on the market
            try:
                TypeStatistics.objects.get(item_type=item_type, region=region).delete()
            except TypeStatistics.DoesNotExist:
                pass
            except Exception as e:
                logger.exception(e)


@shared_task()
def update_managed_supply_configs():
    logger.debug("update_managed_supply_configs()")
    for managed_supply_config in ManagedSupplyConfig.objects.all():
        logger.debug(
            f"update_managed_supply_configs(), Queuing up celery task for managed_supply_config {managed_supply_config.managed_app_reason}")
        if managed_supply_config.managed_app == 'fittings' and fittings_active() is True:
            update_managed_supply_config_fittings_fit(managed_supply_config)
