# https://developers.google.com/optimization/lp/stigler_diet
# https://github.com/cdanis/kantorotanium/blob/master/kantorotanium/__main__.py
import logging
from math import ceil

from discord.commands import SlashCommandGroup
from discord.ext import commands
from eve_sde.models import ItemType, ItemTypeMaterial
from ortools.linear_solver import pywraplp

from marketmanager.app_settings import (
    MARKETMANAGER_COG_OPTIMIZE_FREIGHT_COST,
    MARKETMANAGER_COG_OPTIMIZE_REFINE_RATE, MARKETMANAGER_TASK_PRIORITY_ORDERS,
)
from marketmanager.models import Order
from marketmanager.tasks import fetch_markets_region_id_orders

logger = logging.getLogger(__name__)

ASTEROID = 25


async def send_long_message(ctx, message):
    """Helper function to send long messages by splitting them into chunks."""
    char_limit = 2000
    while len(message) > char_limit:
        split_index = message[:char_limit].rfind("\n")
        if split_index == -1:
            split_index = char_limit  # Fallback to hard split
        await ctx.send(message[:split_index])
        message = message[split_index:]
    if message:
        await ctx.send(message)


class MarketManager(commands.Cog):
    """
    Market Management and Tools
    From AA-MarketManager
    """

    def __init__(self, bot):
        self.bot = bot

    marketmanager_commands = SlashCommandGroup("marketmanager", "Market Manager",)

    @marketmanager_commands.command(name="update_orders", description="Return an optimized set of orders for given minerals")
    async def update_publicmarketdata_ores(
            self, ctx, region_id: int = 10000002):
        for item_type in ItemType.objects.filter(item_group__eve_category_id=ASTEROID, item_market_group__isnull=False, published=1):
            fetch_markets_region_id_orders.apply_async(
                args=[region_id, "sell", item_type.id], priority=MARKETMANAGER_TASK_PRIORITY_ORDERS)
        return await ctx.respond("Tasks Queued, Please wait atleast 5 Minutes")

    @marketmanager_commands.command(name="optimize", description="Return an optimized set of orders for given minerals")
    async def optimize(
            self, ctx,
            tritanium: int, pyerite: int, mexallon: int, isogen: int, nocxium: int, zydrine: int, megacyte: int, morphite: int = 0,
            freight_cost: float = MARKETMANAGER_COG_OPTIMIZE_FREIGHT_COST,
            location_id: int = 60003760,
            raw_data: bool = False):

        output_string = []
        refine_cache = {}
        ore_minerals = []

        # Initiate the array, this is used a lot later to iterate over each mineral
        required_minerals = [
            ["Tritanium", tritanium],
            ["Pyerite", pyerite],
            ["Mexallon", mexallon],
            ["Isogen", isogen],
            ["Nocxium", nocxium],
            ["Zydrine", zydrine],
            ["Megacyte", megacyte],
            ["Morphite", morphite]]

        # Build an array of refining data to avoid ever querying it again.
        # I couldn't find a nice way to do these reverse FK's etc in the order query
        # {'Tritanium': {{type_id: quantity}, {}}, 'Mineral': ... }
        # Side note why the fuck did i do it from material upwards, i could have done Type down????
        for mineral in required_minerals:
            mineral_refine_cache = {}
            for _mineral_refine_cache in ItemTypeMaterial.objects.filter(
                    item_type__item_group__eve_category_id=ASTEROID,
                    item_type__item_market_group__isnull=False, item_type__published=1,
                    material_item_type__name__icontains=mineral[0]).values("item_type", "quantity", "item_type__portion_size"):
                mineral_refine_cache.update(
                    {_mineral_refine_cache["item_type"]: _mineral_refine_cache["quantity"] / _mineral_refine_cache["item_type__portion_size"] * MARKETMANAGER_COG_OPTIMIZE_REFINE_RATE})
            refine_cache.update({mineral[0]: dict(mineral_refine_cache)})

        # Here we build out an array of every ore on the market, its price and what it refines into
        # Uses the above cache heavily, the market orders are quite simple
        for order in Order.objects.filter(
                item_type__item_group__eve_category_id=ASTEROID,
                item_type__item_market_group__isnull=False, item_type__published=1, is_buy_order=0,
                location_id=location_id).select_related("item_type"):
            # id like to replace this with a single iterator
            try:
                _tritanium = refine_cache["Tritanium"][order.item_type.id]
            except KeyError:
                _tritanium = 0
            try:
                _pyerite = refine_cache["Pyerite"][order.item_type.id]
            except KeyError:
                _pyerite = 0
            try:
                _mexallon = refine_cache["Mexallon"][order.item_type.id]
            except KeyError:
                _mexallon = 0
            try:
                _isogen = refine_cache["Isogen"][order.item_type.id]
            except KeyError:
                _isogen = 0
            try:
                _nocxium = refine_cache["Nocxium"][order.item_type.id]
            except KeyError:
                _nocxium = 0
            try:
                _zydrine = refine_cache["Zydrine"][order.item_type.id]
            except KeyError:
                _zydrine = 0
            try:
                _megacyte = refine_cache["Megacyte"][order.item_type.id]
            except KeyError:
                _megacyte = 0
            try:
                _morphite = refine_cache["Morphite"][order.item_type.id]
            except KeyError:
                _morphite = 0
            _ore_minerals = [
                f"{order.item_type.name} @ {order.price}",
                order.item_type.volume,
                float(order.price) + (freight_cost * order.item_type.volume),
                order.volume_remain,
                _tritanium,
                _pyerite,
                _mexallon,
                _isogen,
                _nocxium,
                _zydrine,
                _megacyte,
                _morphite,
            ]
            ore_minerals.append(_ore_minerals)
        solver = pywraplp.Solver.CreateSolver("GLOP_LINEAR_PROGRAMMING")

        # Define all our variables in an array
        ores = [solver.NumVar(0, item[3], item[0]) for item in ore_minerals]

        # Create the constraints (Requirement), one per mineral.
        # Add coefficients/variable (Refine value), each ore ^ once per mineral
        constraints = []
        for i, mineral in enumerate(required_minerals):
            constraints.append(solver.Constraint(mineral[1], solver.infinity()))
            for j, item in enumerate(ore_minerals):
                constraints[i].SetCoefficient(ores[j], item[i + 4])

        # Objective function: Minimize the sum of price of ores.
        # This should also set the minimum viable price to one item
        # not sure if/how this affects steps
        objective = solver.Objective()
        for k, ore in enumerate(ores):
            objective.SetCoefficient(ore, ore_minerals[k][2])
        objective.SetMinimization()

        output_string.append("")
        output_string.append(
            f"Solver: {solver.SolverVersion()} Variables: {solver.NumVariables()} Constraints: {solver.NumConstraints()} ")

        status = solver.Solve()
        if status != solver.OPTIMAL:
            output_string.append("The problem does not have an optimal solution!")
            if status == solver.FEASIBLE:
                output_string.append("A potentially suboptimal solution was found.")
            else:
                output_string.append("The solver could not solve the problem.")
                return await ctx.respond("\n".join(output_string))
        required_minerals_result = [0] * len(required_minerals)

        if raw_data is False:
            output_string.append("### Required Ores:")
            output_string.append("```")
            for i, ore in enumerate(ores):
                if ore.solution_value() > 0.0:
                    output_string.append(f"{ore_minerals[i][0]} * {ceil(ore.solution_value())}")
                    for j, _ in enumerate(required_minerals):
                        required_minerals_result[j] += ore_minerals[i][j + 4] * \
                            ore.solution_value()  # i think this sums up minerals to output later
        else:
            output_string.append("### Buy All:")
            output_string.append("```")
            for i, ore in enumerate(ores):
                if ore.solution_value() > 0.0:
                    output_string.append(f"{ore_minerals[i][0].split('@')[0]} {ceil(ore.solution_value())}")
                    for j, _ in enumerate(required_minerals):
                        required_minerals_result[j] += ore_minerals[i][j + 4] * \
                            ore.solution_value()  # i think this sums up minerals to output later
        output_string.append("``` ")

        await send_long_message(ctx, "\n".join(output_string))
        output_string = []

        if raw_data is False:
            output_string.append("### Mineral Status:")
            output_string.append("```")
            for i, mineral in enumerate(required_minerals):
                output_string.append(
                    f"{mineral[0]} {required_minerals_result[i]:,.2f} / {mineral[1]} ({required_minerals_result[i] / mineral[1] * 100:.1f}%) ")
        else:
            output_string.append("### Output Minerals:")
            output_string.append("```")
            for i, mineral in enumerate(required_minerals):
                output_string.append(f"{mineral[0]} {required_minerals_result[i]:,.2f}")
        output_string.append("```")

        output_string.append(f"Cost for Requested Minerals: ISK `{objective.Value():,.2f}`")
        output_string.append("Calculation Stats:")
        output_string.append(f"Problem solved in {solver.wall_time():d} milliseconds")
        output_string.append(f"Problem solved in {solver.iterations():d} iterations")

        await send_long_message(ctx, "\n".join(output_string))


def setup(bot):
    bot.add_cog(MarketManager(bot))
