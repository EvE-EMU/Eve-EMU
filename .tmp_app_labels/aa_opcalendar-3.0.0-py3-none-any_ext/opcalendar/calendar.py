from calendar import HTMLCalendar
from datetime import date, datetime
from itertools import chain

from allianceauth.services.hooks import get_extension_logger
from django.db.models import F, Q
from django.utils import timezone

from .app_settings import (
    OPCALENDAR_DISPLAY_MOONMINING,
    OPCALENDAR_DISPLAY_MOONMINING_TAGS,
    OPCALENDAR_DISPLAY_STRUCTURETIMERS,
    moonmining_active,
    structuretimers_active,
)
from .models import Event, IngameEvents

if structuretimers_active():
    from structuretimers.models import Timer

if moonmining_active():
    from moonmining.models import Extraction

logger = get_extension_logger(__name__)


class Calendar(HTMLCalendar):
    def __init__(self, year=None, month=None, user=None):
        self.year = year
        self.month = month
        self.user = user
        super(Calendar, self).__init__()

    def formatday(
        self, day, events, ingame_events, structuretimer_events, moonmining_events
    ):
        structuretimers_per_day = []
        moonmining_per_day = []
        events_per_day = events.filter(start_time__day=day)
        ingame_events_per_day = ingame_events.filter(event_start_date__day=day)

        if structuretimers_active() and OPCALENDAR_DISPLAY_STRUCTURETIMERS:
            structuretimers_per_day = structuretimer_events.filter(start_time__day=day)

        if moonmining_active() and OPCALENDAR_DISPLAY_MOONMINING:
            moonmining_per_day = moonmining_events.filter(chunk_arrival_at__day=day)

        all_events_per_day = sorted(
            chain(
                ((event, f"event-{event.id}") for event in events_per_day),
                (
                    (event, f"ingame-{event.event_id}")
                    for event in ingame_events_per_day
                ),
                ((event, f"struct-{event.id}") for event in structuretimers_per_day),
                ((event, f"moon-{event.id}") for event in moonmining_per_day),
            ),
            key=lambda item: (
                item[0].start_time
                if hasattr(item[0], "start_time")
                else item[0].chunk_arrival_at
            ),
        )

        d = ""
        standardized_events_per_day = []
        if day != 0:
            for event, unique_id in all_events_per_day:
                standardized_event = {
                    "id": unique_id,
                    "start_time": (
                        event.start_time
                        if hasattr(event, "start_time")
                        else event.chunk_arrival_at
                    ),
                    "end_time": getattr(event, "end_time", None),
                    "title": getattr(event, "title", "Unnamed Event"),
                    "description": getattr(event, "description", ""),
                    "type": type(event).__name__,
                }
                standardized_events_per_day.append(standardized_event)

                if type(event).__name__ == "Timer":
                    # Determine the objective type for the timer
                    objective_map = {
                        "HO": "Hostile",
                        "FR": "Friendly",
                        "NE": "Neutral",
                        "UN": "Undefined",
                    }
                    objective_verbosed = objective_map.get(event.objective, "Undefined")

                    # Generate the HTML for the Timer event
                    d += (
                        f'<div class="event {"past-event" if datetime.now(timezone.utc) > event.date else "future-event"} event-structuretimer">'
                        f'<span id="event-time-{unique_id}">{event.date.strftime("%H:%M")}</span>'
                        f"<span>{event.eve_solar_system.name} - {event.structure_type.name}</span>"
                        f"<span><i> {objective_verbosed} structure timer</i></span>"
                        f"</div>"
                    )

                elif type(event).__name__ == "Extraction":
                    if self.user.has_perm("moonmining.extractions_access"):
                        # Extract relevant details for the extraction event
                        refinery = event.refinery.name
                        system = (
                            event.refinery.moon.eve_moon.eve_planet.eve_solar_system.name
                        )
                        structure = refinery.replace(system, "")

                        # Generate the display name with or without moon tags
                        display_name = (
                            (
                                event.refinery.moon.rarity_tag_html
                                + '<span class="event-moon-name">'
                                + structure[3:]
                                + "</span>"
                            )
                            if OPCALENDAR_DISPLAY_MOONMINING_TAGS
                            else "<span>" + structure[3:] + "</span>"
                        )

                        # Generate the HTML for the Extraction event
                        d += (
                            f'<a class="nostyling" href="/moonmining/extraction/{event.id}?new_page=yes">'
                            f'<div class="event {"past-event" if datetime.now(timezone.utc) > event.chunk_arrival_at else "future-event"} event-moonmining">'
                            f'<span id="event-time-{unique_id}">{event.chunk_arrival_at.strftime("%H:%M")}</span>'
                            f"<span>{event.refinery.moon.eve_moon.name}</span>"
                            f'<div class="event-moon-details">'
                            f"{display_name}"
                            f"</div>"
                            f"</div>"
                            f"</a>"
                        )

                elif type(event).__name__ in ["Event", "IngameEvents"]:
                    # Determine start time, title, and owner for the event
                    start_time = (
                        event.start_time.strftime("%H:%M")
                        if hasattr(event, "start_time")
                        else event.event_start_date.strftime("%H:%M")
                    )
                    title = (
                        f"{event.operation_type.ticker} {event.title}"
                        if hasattr(event, "operation_type")
                        else event.title
                    )
                    owner = (
                        event.host.community
                        if hasattr(event, "host")
                        else event.owner_name
                    )

                    # Generate the HTML for the Event or IngameEvents
                    d += (
                        f"<style>{event.get_event_styling}</style>"
                        f'<a class="nostyling" href="{event.get_html_url}">'
                        f'<div class="event {event.get_date_status} {event.get_visibility_class} {event.get_category_class} {event.external_tag}">'
                        f'<span id="event-time-{unique_id}">{start_time}</span>'
                        f"<span><b>{title}</b></span>"
                        f"<span><i>{owner}</i></span>"
                        f"</div>"
                        f"</a>"
                    )

            if date.today() == date(self.year, self.month, day):
                return (
                    f"<td class='today'><div class='date'>{day}</div> {d}</td>",
                    standardized_events_per_day,
                )
            return (
                f"<td><div class='date'>{day}</div> {d}</td>",
                standardized_events_per_day,
            )
        return "<td></td>", standardized_events_per_day

    def formatweek(
        self, theweek, events, ingame_events, structuretimer_events, moonmining_events
    ):
        week = ""
        all_events = []
        for d, weekday in theweek:
            day_html, day_events = self.formatday(
                d, events, ingame_events, structuretimer_events, moonmining_events
            )
            week += day_html
            all_events.extend(day_events)
        return f"<tr> {week} </tr>", all_events

    def formatmonth(self, withyear=True):
        events = (
            Event.objects.filter(
                start_time__year=self.year,
                start_time__month=self.month,
            )
            .filter(
                Q(event_visibility__restricted_to_group__in=self.user.groups.all())
                | Q(event_visibility__restricted_to_group__isnull=True),
            )
            .filter(
                Q(event_visibility__restricted_to_state=self.user.profile.state)
                | Q(event_visibility__restricted_to_state__isnull=True),
            )
        )

        ingame_events = (
            IngameEvents.objects.filter(
                event_start_date__year=self.year, event_start_date__month=self.month
            )
            .annotate(start_time=F("event_start_date"), end_time=F("event_end_date"))
            .filter(
                Q(
                    owner__event_visibility__restricted_to_group__in=self.user.groups.all()
                )
                | Q(owner__event_visibility__restricted_to_group__isnull=True),
            )
            .filter(
                Q(owner__event_visibility__restricted_to_state=self.user.profile.state)
                | Q(owner__event_visibility__restricted_to_state__isnull=True),
            )
        )

        if structuretimers_active() and OPCALENDAR_DISPLAY_STRUCTURETIMERS:
            structuretimer_events = (
                Timer.objects.all()
                .visible_to_user(self.user)
                .annotate(start_time=F("date"))
                .filter(date__year=self.year, date__month=self.month)
            )
        else:
            structuretimer_events = Event.objects.none()

        if moonmining_active() and OPCALENDAR_DISPLAY_MOONMINING:
            moonmining_events = (
                Extraction.objects.all()
                .annotate(start_time=F("chunk_arrival_at"))
                .filter(
                    chunk_arrival_at__year=self.year, chunk_arrival_at__month=self.month
                )
                .exclude(status="CN")
            )
        else:
            moonmining_events = Event.objects.none()

        logger.debug(
            "Returning %s extractions, display setting is %s. List is: %s"
            % (
                moonmining_events.count(),
                OPCALENDAR_DISPLAY_MOONMINING,
                moonmining_events,
            )
        )

        logger.debug("Returning %s ingame events" % ingame_events.count())

        cal = '<table class="calendar">\n'
        cal += f"{self.formatmonthname(self.year, self.month, withyear=withyear)}\n"
        cal += f"{self.formatweekheader()}\n"

        all_events_per_month = []

        for week in self.monthdays2calendar(self.year, self.month):
            week_html, week_events = self.formatweek(
                week, events, ingame_events, structuretimer_events, moonmining_events
            )
            cal += f"{week_html}\n"
            all_events_per_month.extend(week_events)

        cal += "</table>"

        return cal, all_events_per_month
