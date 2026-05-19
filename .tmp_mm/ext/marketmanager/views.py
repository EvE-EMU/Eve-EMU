import datetime
import json
from collections.abc import Iterable
from typing import Any

from eve_sde.models import ItemMarketGroup, ItemType, NPCStation, Region

from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import F, Sum
from django.db.models.expressions import Case, When
from django.http import HttpResponseRedirect
from django.http.response import HttpResponse, JsonResponse
from django.shortcuts import redirect, render

from allianceauth.services.hooks import get_extension_logger
from esi.decorators import token_required

from marketmanager.app_settings import (
    MARKETMANAGER_TYPESTATISTICS_MINIMUM_ORDER_COUNT,
)
from marketmanager.models import (
    Order, PublicConfig, Structure, SupplyConfig, TypeStatistics,
)

logger = get_extension_logger(__name__)

CHARACTER_SCOPES = [
    'esi-markets.read_character_orders.v1',
    'esi-markets.structure_markets.v1',
    'esi-universe.read_structures.v1',
]

CORPORATION_SCOPES = [
    'esi-markets.read_corporation_orders.v1',
    'esi-markets.structure_markets.v1',
    'esi-characters.read_corporation_roles.v1',
    'esi-corporations.read_structures.v1',
    'esi-universe.read_structures.v1',
]


@login_required
@permission_required("marketmanager.basic_market_browser")
def marketbrowser(request) -> HttpResponse:
    region_id = request.GET.get('region_id', None)
    type_id = request.GET.get('type_id', None)
    all_regions = PublicConfig.get_solo().fetch_regions.all()
    parent_market_groups = ItemMarketGroup.objects.filter(
        parent_group_id__isnull=True)

    try:
        item_type = ItemType.objects.get(id=type_id) if type_id else None
    except ItemType.DoesNotExist:
        item_type = None

    try:
        region = Region.objects.get(id=region_id) if region_id else None
    except Region.DoesNotExist:
        region = None

    if item_type is not None:
        item_type_icon_url = f"https://images.evetech.net/types/{item_type.id}/icon?size=256"
    else:
        item_type_icon_url = None

    render_items = {
        "all_regions": all_regions,
        "parent_market_groups": parent_market_groups,
        "region": region,
        "item_type": item_type,
        "item_type_icon_url": item_type_icon_url,
        "type_statistics": type_statistics(item_type=item_type, region=region),
    }
    return render(request, "marketmanager/marketbrowser-bs5.html", render_items)


@login_required
@permission_required("marketmanager.basic_market_watches")
def marketwatches(request) -> HttpResponse:

    watchconfigs = SupplyConfig.objects.all().annotate(
        missing_volume=F("volume") - F("last_result_volume")
    ).filter(
        missing_volume__gt=0)
    render_items = {
        "watchconfigs": watchconfigs,
    }
    return render(request, "marketmanager/marketwatches-bs5.html", render_items)


@login_required
@permission_required("marketmanager.basic_market_browser")
def marketbrowser_autocomplete(request) -> HttpResponse:
    search_query = None
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':  # is_ajax
        search_query = request.GET.get('term')

    autocomplete_query = ItemType.objects.filter(
        name__icontains=search_query,
        market_group__isnull=False,
        published=1
    ).order_by("name")

    result = []
    for possible in autocomplete_query:
        data = {}
        data['label'] = possible.name
        data['value'] = possible.id
        result.append(data)
    dump = json.dumps(result)

    mimetype = 'application/json'
    return HttpResponse(dump, mimetype)


@login_required
@permission_required("marketmanager.basic_market_browser")
def marketbrowser_buy_orders(request) -> JsonResponse:
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':  # is_ajax
        region_id = request.GET.get('region_id', None)
        type_id = request.GET.get('type_id', None)
    else:
        region_id = None
        type_id = None

    if request.user.has_perm("marketmanager.order_highlight_user"):
        user_characters = request.user.character_ownerships.all(
        ).select_related('character').values('character')
    else:
        user_characters = []

    if request.user.has_perm("marketmanager.order_highlight_corporation"):
        user_corporation_ids = request.user.character_ownerships.all().select_related(
            'character__corporation_id').values('character__corporation_id')
    else:
        user_corporation_ids = []

    buy_orders = Order.objects.filter(
        item_type=type_id,
        is_buy_order=True
    ).annotate(
        user_is_owner=Case(
            When(
                issued_by_character__in=user_characters,
                then=True
            ),
            default=False
        ),
        corporation_is_owner=Case(
            When(
                issued_by_corporation__corporation_id__in=user_corporation_ids,
                then=True
            ),
            default=False
        ),
    ).values(
        'volume_remain',
        'price',
        'location_id',
        'issued',
        'duration',
        'region__name',
        'updated_at',
        'user_is_owner',
        'corporation_is_owner'
    )
    if region_id is not None:
        buy_orders = buy_orders.filter(
            region=region_id
        )

    buy_order_locations = []
    for order in buy_orders:
        buy_order_locations.append(order['location_id'])
    station_resolved, structures_resolved = bulk_location_resolver(buy_order_locations)

    for order in buy_orders:
        if station_resolved.get(order['location_id']) is not None:
            order['location_resolved'] = station_resolved[order['location_id']].name
        else:
            try:
                order['location_resolved'] = structures_resolved[order['location_id']].name
            except KeyError:
                order['location_resolved'] = order['location_id']
        order["expiry_calculated"] = order["issued"] + \
            datetime.timedelta(days=order["duration"])

    return JsonResponse({"buy_orders": list(buy_orders)})


@login_required
@permission_required("marketmanager.basic_market_browser")
def marketbrowser_sell_orders(request) -> JsonResponse:
    if request.headers.get('x-requested-with') == 'XMLHttpRequest':  # is_ajax
        region_id = request.GET.get('region_id', None)
        type_id = request.GET.get('type_id', None)
    else:
        region_id = None
        type_id = None

    if request.user.has_perm("marketmanager.order_highlight_user"):
        user_characters = request.user.character_ownerships.all(
        ).select_related('character').values('character')
    else:
        user_characters = []

    if request.user.has_perm("marketmanager.order_highlight_corporation"):
        user_corporation_ids = request.user.character_ownerships.all().select_related(
            'character__corporation_id').values('character__corporation_id')
    else:
        user_corporation_ids = []

    # Sell Orders
    sell_orders = Order.objects.filter(
        item_type=type_id,
        is_buy_order=False
    ).annotate(
        user_is_owner=Case(
            When(
                issued_by_character__in=user_characters,
                then=True
            ),
            default=False
        ),
        corporation_is_owner=Case(
            When(
                issued_by_corporation__corporation_id__in=user_corporation_ids,
                then=True
            ),
            default=False
        ),
    ).values(
        'volume_remain',
        'price',
        'location_id',
        'issued',
        'duration',
        'region__name',
        'updated_at',
        'order_id',
        'user_is_owner',
        'corporation_is_owner'
    )

    if region_id is not None:
        sell_orders = sell_orders.filter(
            region=region_id
        )

    sell_order_locations = []
    for order in sell_orders:
        sell_order_locations.append(order['location_id'])
    station_resolved, structures_resolved = bulk_location_resolver(sell_order_locations)

    for order in sell_orders:
        if station_resolved.get(order['location_id']) is not None:
            order['location_resolved'] = station_resolved[order['location_id']].name
        else:
            try:
                order['location_resolved'] = structures_resolved[order['location_id']].name
            except KeyError:
                order['location_resolved'] = order['location_id']
        order["expiry_calculated"] = order["issued"] + \
            datetime.timedelta(days=order["duration"])

    return JsonResponse({"sell_orders": list(sell_orders)})


@login_required
@permission_required("marketmanager.basic_market_browser")
def item_selector(request) -> HttpResponse:
    data = ItemMarketGroup.objects.all()
    return render(request, "marketmanager/item_selector.html", {"market_groups": data})


@login_required
@token_required(scopes=CHARACTER_SCOPES)
def add_char(request, token) -> HttpResponseRedirect:
    return redirect('marketmanager:marketbrowser')


@login_required
@token_required(scopes=CORPORATION_SCOPES)
def add_corp(request, token) -> HttpResponseRedirect:
    return redirect('marketmanager:marketbrowser')


def location_resolver(location_id: int) -> str:
    if location_id >= 60000000 and location_id <= 64000000:
        # NPCStation (Range: 60000000 - 64000000)
        return NPCStation.objects.get(id=location_id).name
    else:
        try:
            return Structure.objects.get(structure_id=location_id).name
        except Exception as e:
            logger.exception(e)
            return str(location_id)


def bulk_location_resolver(location_ids: Iterable[int]) -> tuple[dict[int, NPCStation], dict[int, Structure]]:
    bulk_station_ids = []
    bulk_structure_ids = []

    for location_id in location_ids:
        if location_id >= 60000000 and location_id <= 64000000:
            # NPCStation (Range: 60000000 - 64000000)
            bulk_station_ids.append(location_id)
        else:
            bulk_structure_ids.append(location_id)

    station_resolver = NPCStation.objects.in_bulk(bulk_station_ids)
    structure_resolver = Structure.objects.in_bulk(bulk_structure_ids)

    return station_resolver, structure_resolver


def type_statistics(item_type: ItemType | None, region: Region | None) -> dict[str, Any]:
    # Returns a specific set of stats for the item_details template
    orders = Order.objects.filter(item_type=item_type)
    if region is not None:
        orders = orders.filter(
            region=region
        )
    try:
        order_stats = TypeStatistics.objects.get(
            item_type=item_type, region=region)
    except ObjectDoesNotExist:
        return {
            'buy_fifth_percentile': 0,
            'sell_fifth_percentile': 0,
            'buy_weighted_average': 0,
            'sell_weighted_average': 0,
            'buy_median': 0,
            'sell_median': 0,
            'buy_volume': orders.filter(is_buy_order=True).aggregate(volume=Sum(F('volume_remain')))["volume"],
            'sell_volume': orders.filter(is_buy_order=False).aggregate(volume=Sum(F('volume_remain')))["volume"],
            'explain': f"TypeStatistics have not been calculated yet, or skipped due to less than {MARKETMANAGER_TYPESTATISTICS_MINIMUM_ORDER_COUNT} orders"
        }
    return {
        'buy_fifth_percentile': order_stats.buy_fifth_percentile,
        'sell_fifth_percentile': order_stats.sell_fifth_percentile,
        'buy_weighted_average': order_stats.buy_weighted_average,
        'sell_weighted_average': order_stats.sell_weighted_average,
        'buy_median': order_stats.buy_median,
        'sell_median': order_stats.sell_median,
        'buy_volume': orders.filter(is_buy_order=True).aggregate(volume=Sum(F('volume_remain')))["volume"],
        'sell_volume': orders.filter(is_buy_order=False).aggregate(volume=Sum(F('volume_remain')))["volume"],
        'explain': None
    }
