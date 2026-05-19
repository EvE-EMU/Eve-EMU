# Cog Stuff
import logging

# OPCALENDAR
import operator
import os
from datetime import datetime
from itertools import chain

# AA Contexts
from aadiscordbot.app_settings import get_site_url
from allianceauth.services.modules.discord.models import DiscordUser
from app_utils.urls import static_file_absolute_url
from discord.colour import Color
from discord.commands import Option
from discord.embeds import Embed
from discord.ext import commands
from django.conf import settings
from django.db.models import F, Q

from opcalendar.app_settings import OPCALENDAR_DISCORD_OPS_DISPLAY_EXTERNAL
from opcalendar.models import Event, EventHost, IngameEvents

logger = logging.getLogger(__name__)

# i dont want to do this, but the below object get wont work without it, investigate.
os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"


class Ops(commands.Cog):
    """
    Return upcoming events as a discord DM
    """

    def __init__(self, bot):
        self.bot = bot

    hosts = EventHost.objects.all().values_list("community", flat=True)

    @commands.command(pass_context=True)
    async def ops(self, ctx):
        """
        Sends a direct message about the upcoming events visible for the user
        """
        await ctx.trigger_typing()

        # Get authod ID
        author_id = ctx.message.author.id

        user_argument = ctx.message.content[5:]

        embed = _get_events(author_id, user_argument)

        await ctx.author.send(embed=embed)

        confirm = _confirm_ops_in_channel()

        return await ctx.reply(embed=confirm)

    @commands.slash_command(name="ops", guild_ids=[int(settings.DISCORD_GUILD_ID)])
    async def ops_slash(
        self,
        ctx,
        host: Option(
            str,
            choices=hosts,
            required=False,
        ),
    ):
        """
        Get upcoming events as DM. Can be filtered by hosts (optional)
        """

        # Get attributes
        author_id = ctx.author.id

        user_argument = host

        embed = _get_events(author_id, user_argument)

        await ctx.author.send(embed=embed)

        confirm = _confirm_ops_in_channel()

        return await ctx.respond(embed=confirm)


def _hosts(hosts):
    hosts = [x.community for x in hosts]

    if hosts:
        return ", ".join(hosts)
    else:
        return None


def _get_events(author, user_argument):
    url = get_site_url()

    today = datetime.today()

    if not user_argument:
        host = "all hosts"

    else:
        host = user_argument

    # Get user if discord service is active
    try:
        discord_user = DiscordUser.objects.get(uid=author)

        user = discord_user.user

        discord_active = True

    except Exception:
        logger.error("Discord service is not active for user")

        embed = Embed(title="Command failed")
        embed.colour = Color.red()
        embed.set_thumbnail(url=static_file_absolute_url("opcalendar/terminate.png"))
        embed.description = "Activate the [discord service]({}/services) to access this command.".format(
            url
        )
        discord_active = False

        return embed

    if discord_active:
        # Get normal events
        # Filter by groups and states
        events = (
            Event.objects.filter(
                Q(event_visibility__restricted_to_group__in=user.groups.all())
                | Q(event_visibility__restricted_to_group__isnull=True),
            )
            .filter(
                Q(event_visibility__restricted_to_state=user.profile.state)
                | Q(event_visibility__restricted_to_state__isnull=True),
            )
            .filter(start_time__gte=today)
        )
        if user_argument:
            events = events.filter(host__community=host)

        # Get ingame events
        # Filter by groups and states
        ingame_events = (
            IngameEvents.objects.annotate(
                start_time=F("event_start_date"),
                end_time=F("event_end_date"),
            )
            .filter(
                Q(owner__event_visibility__restricted_to_group__in=user.groups.all())
                | Q(owner__event_visibility__restricted_to_group__isnull=True),
            )
            .filter(
                Q(owner__event_visibility__restricted_to_state=user.profile.state)
                | Q(owner__event_visibility__restricted_to_state__isnull=True),
            )
            .filter(start_time__gte=today)
        )

        hosts = EventHost.objects.all()

        if not OPCALENDAR_DISCORD_OPS_DISPLAY_EXTERNAL:
            hosts = hosts.filter(external=False)

        hosts = _hosts(hosts)

        if user_argument:
            ingame_events = ingame_events.filter(host__community=host)

        # Combine events, limit to 10 events
        all_events = sorted(
            chain(events, ingame_events),
            key=operator.attrgetter("start_time"),
        )[:10]

        embed = Embed(title="Scheduled Opcalendar Events")

        embed.set_thumbnail(url=static_file_absolute_url("opcalendar/calendar.png"))

        embed.colour = Color.blue()

        embed.description = "List view of the next 10 upcoming operations for {}. A calendar view is located in [here]({}/opcalendar).\n\nFiltering: To filter events for a specific host add the name after the command ie. `/ops my coalition`\n\nAvailable hosts: *{}*".format(
            host, url, hosts
        )

        # Format all events and ingame events
        for event in all_events:
            if isinstance(event, Event):
                embed.add_field(
                    name="Event: {0} {1}".format(
                        event.title, event.operation_type.ticker
                    ),
                    value="Host: {0}\nFC: {1}\nDoctrine: {2}\nLocation: {3}\nTime: {4}\n[Details]({5}/opcalendar/event/{6}/details/)\n".format(
                        event.host,
                        event.fc,
                        event.doctrine,
                        event.formup_system,
                        event.start_time,
                        url,
                        event.id,
                    ),
                    inline=False,
                )
            if isinstance(event, IngameEvents):
                embed.add_field(
                    name="Ingame Event: {0}".format(event.title),
                    value="Host: {0}\n Time:{1}\n[Details]({2}/opcalendar/ingame/event/{3}/details/)".format(
                        event.owner_name,
                        event.start_time,
                        url,
                        event.event_id,
                    ),
                    inline=False,
                )

        discord_active = False

        return embed


def _confirm_ops_in_channel():
    embed = Embed(title="Events sent as DM!")
    embed.colour = Color.green()

    return embed


def setup(bot):
    bot.add_cog(Ops(bot))
