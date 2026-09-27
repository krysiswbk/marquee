"""Sanitized, allowlisted Home Assistant calendar events."""
import json
import os
import re
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .model import Context, EventState, parse_time
from .provider import Provider


PLACEHOLDER = re.compile(r"^(?:tba|tbd|unknown|untitled|to be (?:announced|determined))$", re.I)


class CalendarProvider(Provider):
    name = "calendar"
    refresh_seconds = 300
    stale_seconds = 7200

    def fetch(self):
        try:
            with open(os.path.join(self.data_dir, "ha-calendar-events.json")) as handle:
                feed = json.load(handle)
            if self.clock() - float(feed.get("updated", 0)) > self.stale_seconds:
                return {"events": []}
            return feed
        except (OSError, ValueError, TypeError):
            return {"events": []}

    def _when(self, value, all_day=False):
        if all_day and isinstance(value, str) and len(value) == 10:
            zone = ZoneInfo(self.config.get("timezone", "America/Toronto"))
            return datetime.combine(datetime.fromisoformat(value).date(), time(), zone).astimezone(timezone.utc)
        return parse_time(value)

    def contexts(self, payload, now):
        contexts, seen, birthdays = [], set(), {}
        zone = ZoneInfo(self.config.get("timezone", "America/Toronto"))
        today = now.astimezone(zone).date()
        horizon = now + timedelta(days=int(self.config.get("lookahead_days", 14)))
        for event in payload.get("events", []) if isinstance(payload, dict) else []:
            title = str(event.get("summary", "")).strip()
            if not title or PLACEHOLDER.fullmatch(title.strip("[]()")):
                continue
            calendar = f"{event.get('entity_id', '')} {event.get('calendar_name', '')}".lower()
            birthday = bool(re.search(r"birthday|b-day|bday", calendar + " " + title, re.I))
            # Apply this at consumption too, so previously cached Bills feeds
            # disappear immediately after an upgrade.
            if re.search(r"(?:^|[\W_])bills(?:$|[\W_])", calendar) or (
                    not birthday and re.search(r"\b(?:bill|invoice|payment due|rent due|student loan|mortgage|credit card payment|loan repayment)\b", title, re.I)):
                continue
            all_day = bool(event.get("all_day"))
            starts = self._when(event.get("start"), all_day)
            ends = self._when(event.get("end"), all_day) or (starts + timedelta(days=1) if starts else None)
            if not starts or not ends or ends <= now or starts > horizon:
                continue
            if birthday:
                day = starts.astimezone(zone).date()
                if today <= day <= today + timedelta(days=int(self.config.get("lookahead_days", 21))):
                    identity = (re.sub(r"[^a-z0-9]", "", title.casefold()), day)
                    birthdays.setdefault(identity, (day, title))
                continue
            identity = (str(event.get("entity_id", "")), str(event.get("uid", "")) or title.casefold(), starts)
            if identity in seen:
                continue
            seen.add(identity)
            seconds = (starts - now).total_seconds()
            state = EventState.LIVE if starts <= now < ends else (
                EventState.STARTING_SOON if seconds <= 2 * 3600 else EventState.UPCOMING)
            days = max(0, (starts.astimezone(zone).date() - today).days)
            when = "Today" if days == 0 else "Tomorrow" if days == 1 else starts.astimezone(zone).strftime("%a, %b %-d")
            if not all_day:
                when += starts.astimezone(zone).strftime(" · %-I:%M %p")
            event_priority = max(0, min(100, int(event.get("priority", self.config.get("priority", 40)))))
            configured_targets = self.config.get("targets", ["kiosk"])
            requested_targets = event.get("targets", configured_targets)
            targets = [x for x in requested_targets if x in configured_targets]
            cast_allowed = (self.config.get("allow_cast", False) and "hubs" in targets and
                            event_priority >= int(self.config.get("cast_min_priority", 95)))
            if not cast_allowed:
                targets = [x for x in targets if x != "hubs"]
            contexts.append(Context(
                id=f"calendar:{event.get('entity_id','event')}:{event.get('uid') or title}:{starts.isoformat()}",
                provider=self.name, type="calendar_event", subtype="all_day" if all_day else "timed",
                title=title, subtitle=when, body=str(event.get("description", ""))[:240],
                start_time=starts, end_time=ends, event_state=state, priority=event_priority,
                relevance=85 if days <= 1 else 65, urgency=100 if state == EventState.LIVE else
                    max(35, 95 - int(max(0, seconds) / 3600) * 5), significance=55,
                expires_at=ends, source_url=str(event.get("url", "")), targets=targets or ["kiosk"],
                icon="mdi:calendar-star", accent=str(event.get("accent", "#38bdf8"))[:20],
                stats=[str(event.get("calendar_name", "Calendar"))[:100]],
                raw={"castTakeover": cast_allowed, "allDay": all_day,
                     "location": str(event.get("location", ""))[:160]}))
        if birthdays:
            upcoming = sorted(birthdays.values(), key=lambda item: (item[0], item[1].casefold()))
            day, title = upcoming[0]
            def label(date):
                days = (date - today).days
                relative = "Today" if days == 0 else "Tomorrow" if days == 1 else f"In {days} days"
                return f"{relative} · {date.strftime('%b %-d')}"
            midnight = datetime.combine(today + timedelta(days=1), time(), zone)
            contexts.append(Context(
                id="calendar:upcoming-birthdays", provider=self.name,
                type="calendar_event", subtype="birthday_rollup",
                title=title, subtitle=label(day),
                body="Coming up" if len(upcoming) > 1 else "The next birthday in your household calendars",
                start_time=datetime.combine(day, time(), zone),
                end_time=datetime.combine(day + timedelta(days=1), time(), zone),
                event_state=EventState.LIVE if day == today else EventState.UPCOMING,
                priority=int(self.config.get("priority", 40)), relevance=90,
                urgency=75 if day == today else 55, significance=70,
                expires_at=midnight, targets=["kiosk"], icon="mdi:cake-variant",
                accent="#f7b2d9", stats=[f"{name} · {label(date)}" for date, name in upcoming[1:]],
                raw={"status": "Birthday today" if day == today else "Next birthday",
                     "allDay": True, "castTakeover": False}))
        return sorted(contexts, key=lambda item: item.start_time)
