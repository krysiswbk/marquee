"""ESPN-backed followed-sport providers.

These adapters normalize schedules/results only. Casting and display selection
belong to the application and arbitration layers.
"""
from datetime import timedelta
import json
import subprocess

from .model import Context, EventState, parse_time
from .provider import Provider
from .provider import HttpClient


def _state(item):
    return (((item.get("status") or {}).get("type") or {}).get("state") or "pre").lower()


def _side(item):
    participant = item.get("team") or item.get("athlete") or {}
    logos = participant.get("logos") or []
    flag = participant.get("flag") or {}
    headshot = participant.get("headshot") or {}
    return {
        "name": participant.get("displayName") or participant.get("shortDisplayName") or "",
        "abbr": participant.get("abbreviation") or "",
        "score": item.get("score") or "",
        "record": ((item.get("records") or [{}])[0]).get("summary", ""),
        "logo": (participant.get("logo") or headshot.get("href") or
                 ((logos or [{}])[0]).get("href", "") or flag.get("href", "")),
    }


def _lifecycle(state, starts, now, starting_minutes):
    if state == "in":
        return EventState.LIVE
    if state == "post":
        return EventState.POST_EVENT
    if starts - now <= timedelta(minutes=starting_minutes):
        return EventState.STARTING_SOON
    return EventState.UPCOMING


def _priority(lifecycle, configured):
    return {EventState.LIVE: configured, EventState.POST_EVENT: configured - 5,
            EventState.STARTING_SOON: configured - 10,
            EventState.UPCOMING: min(50, configured - 30)}[lifecycle]


class ESPNProvider(Provider):
    refresh_seconds = 60
    stale_seconds = 600
    sport_path = ""

    def fetch(self):
        from datetime import datetime, timezone
        now = datetime.fromtimestamp(self.clock(), timezone.utc)
        start, end = now - timedelta(days=1), now + timedelta(days=7)
        dates = start.strftime("%Y%m%d") + "-" + end.strftime("%Y%m%d")
        url = ("https://site.api.espn.com/apis/site/v2/sports/" + self.sport_path
               + "/scoreboard?limit=100&dates=" + dates)
        if type(self.client) is not HttpClient:
            return self.client.json(url, timeout=8)
        # ESPN's edge currently rejects Python/OpenSSL's TLS fingerprint while
        # accepting curl from the same host. This remains bounded, read-only,
        # and isolated inside the ESPN provider transport.
        raw = subprocess.check_output(["curl", "-fsS", "--max-time", "8",
                                       "-H", "Accept: application/json", url],
                                      timeout=10)
        return json.loads(raw)


class NHLProvider(ESPNProvider):
    name = "nhl"
    sport_path = "hockey/nhl"
    reason = "ESPN schedule filtered to followed NHL teams"

    def contexts(self, payload, now):
        teams = {str(x).upper() for x in self.config.get("teams", ["TOR"])}
        pregame = int(self.config.get("pregame_minutes", 120))
        postgame = int(self.config.get("postgame_minutes", 180))
        priority = int(self.config.get("priority", 90))
        values = []
        for event in payload.get("events", []):
            competition = (event.get("competitions") or [{}])[0]
            competitors = competition.get("competitors") or []
            followed = next((x for x in competitors
                             if (x.get("team") or {}).get("abbreviation", "").upper() in teams), None)
            if not followed:
                continue
            starts = parse_time(event.get("date"))
            if not starts:
                continue
            lifecycle = _lifecycle(_state(event), starts, now, pregame)
            if lifecycle == EventState.UPCOMING and starts - now > timedelta(hours=24):
                continue
            opponent = next((x for x in competitors if x is not followed), {})
            status = (((event.get("status") or {}).get("type") or {}).get("shortDetail", ""))
            values.append(Context(
                "nhl:" + str(event.get("id")), self.name, "nhl_" + _state(event),
                (followed.get("team") or {}).get("displayName", "NHL"),
                subtitle=event.get("name", ""), body=(competition.get("venue") or {}).get("fullName", ""),
                start_time=starts, event_state=lifecycle,
                priority=_priority(lifecycle, priority), relevance=100, urgency=90,
                live=lifecycle == EventState.LIVE,
                expires_at=starts + timedelta(hours=6, minutes=postgame),
                targets=["kiosk", "hubs"] if lifecycle in (EventState.LIVE, EventState.POST_EVENT) else ["kiosk"],
                accent="#1f67b1", raw={"left": _side(followed), "right": _side(opponent),
                                        "status": status}))
        return values


def _fight_label(fight):
    sides = [_side(x)["name"] for x in fight.get("competitors", [])]
    weight = (fight.get("type") or {}).get("abbreviation", "")
    return " vs. ".join(filter(None, sides)) + ((" · " + weight) if weight else "")


def _result(fight):
    sides = fight.get("competitors") or []
    winner = next((_side(x)["name"] for x in sides if x.get("winner")), "")
    loser = next((_side(x)["name"] for x in sides if not x.get("winner")), "")
    status = fight.get("status") or {}
    finish = []
    if status.get("period"):
        finish.append("R" + str(status["period"]))
    if status.get("displayClock"):
        finish.append(str(status["displayClock"]))
    text = winner + ((" def. " + loser) if loser else "") if winner else _fight_label(fight)
    return text + ((" · " + " ".join(finish)) if finish else "")


class MMAProvider(ESPNProvider):
    """Shared fight-card normalization for ESPN MMA promotions."""
    accent = "#d20a0a"

    def contexts(self, payload, now):
        preevent = int(self.config.get("preevent_minutes", 120))
        result_minutes = int(self.config.get("result_minutes", 180))
        priority = int(self.config.get("priority", 90))
        include_contender = bool(self.config.get("include_contender_series", True))
        values = []
        for event in payload.get("events", []):
            title = event.get("name", "")
            if not include_contender and "contender series" in title.lower():
                continue
            starts = parse_time(event.get("date"))
            if not starts:
                continue
            lifecycle = _lifecycle(_state(event), starts, now, preevent)
            if lifecycle == EventState.UPCOMING and starts - now > timedelta(hours=24):
                continue
            fights = event.get("competitions") or []
            active = next((fight for fight in fights if _state(fight) == "in"), None)
            current = active or (fights[-1] if fights else {})
            sides = current.get("competitors") or []
            completed = [fight for fight in fights if _state(fight) == "post"]
            rows = (["LAST · " + _result(fight) for fight in reversed(completed[-2:])]
                    if lifecycle in (EventState.LIVE, EventState.POST_EVENT) else
                    ["CARD · " + _fight_label(fight) for fight in reversed(fights[-2:])])
            status = ((((current.get("status") or {}).get("type") or {}).get("shortDetail"))
                      or (((event.get("status") or {}).get("type") or {}).get("shortDetail", "")))
            venue = (event.get("venues") or [{}])[0].get("fullName", "")
            values.append(Context(
                self.name + ":" + str(event.get("id")), self.name, self.name + "_" + _state(event), title,
                subtitle=_fight_label(current), body=venue, start_time=starts,
                event_state=lifecycle, priority=_priority(lifecycle, priority), relevance=100,
                urgency=90, live=lifecycle == EventState.LIVE,
                expires_at=(now + timedelta(minutes=result_minutes)
                            if lifecycle == EventState.POST_EVENT else
                            starts + timedelta(hours=9)),
                targets=["kiosk", "hubs"] if lifecycle in (EventState.LIVE, EventState.POST_EVENT) else ["kiosk"],
                stats=rows, accent=self.accent,
                raw={"left": _side(sides[0]) if sides else {},
                     "right": _side(sides[1]) if len(sides) > 1 else {}, "status": status}))
        return values


class UFCProvider(MMAProvider):
    name = "ufc"
    sport_path = "mma/ufc"
    reason = "ESPN UFC cards, fights and completed-bout results"


class PFLProvider(MMAProvider):
    name = "pfl"
    sport_path = "mma/pfl"
    reason = "ESPN PFL cards and live bouts; UFC wins overlapping events"
    accent = "#d4a62c"
