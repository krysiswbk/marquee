"""ESPN-backed followed-sport providers.

These adapters normalize schedules/results only. Casting and display selection
belong to the application and arbitration layers.
"""
from datetime import timedelta
import json
import subprocess
from urllib.parse import urlencode

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
        "homeAway": item.get("homeAway") or "",
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
    lookback_days = 1
    lookahead_days = 7

    def fetch(self):
        from datetime import datetime, timezone
        now = datetime.fromtimestamp(self.clock(), timezone.utc)
        start = now - timedelta(days=self.lookback_days)
        end = now + timedelta(days=self.lookahead_days)
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

    # ESPN accepts the scoreboard's `dates` parameter for one calendar day,
    # but currently rejects the otherwise documented ranged form. Keep this
    # deliberately small: the provider refreshes once per minute and the
    # aggregate is cached as one provider snapshot.
    lookback_days = 1
    lookahead_days = 7
    max_dates = 14

    def _summary_url(self, event_id):
        return ("https://site.api.espn.com/apis/site/v2/sports/" + self.sport_path
                + "/summary?event=" + str(event_id))

    @staticmethod
    def _score_details(summary):
        """Normalize ESPN's play-by-play goals and current power-play state."""
        plays = summary.get("plays") or []
        header = summary.get("header") or {}
        competition = (header.get("competitions") or [{}])[0]
        teams = {str((side.get("team") or {}).get("id", "")):
                 (side.get("team") or {}).get("abbreviation", "")
                 for side in competition.get("competitors", [])}
        goals = []
        for play in plays:
            if not play.get("scoringPlay"):
                continue
            clock = (play.get("clock") or {}).get("displayValue", "")
            period = (play.get("period") or {}).get("displayValue", "")
            team_id = str((play.get("team") or {}).get("id", ""))
            text = str(play.get("text", "")).strip()
            when = " ".join(part for part in (period, clock) if part)
            goals.append(" · ".join(part for part in (when, teams.get(team_id, ""), text) if part))

        power_play = ""
        on_ice = summary.get("onIce") or []
        goalie_ids = set()
        for group in (summary.get("boxscore") or {}).get("players", []):
            for stat_group in group.get("statistics", []):
                if str(stat_group.get("name", "")).lower() != "goalies":
                    continue
                for player in stat_group.get("athletes", []):
                    goalie_ids.add(str((player.get("athlete") or {}).get("id", "")))
        skaters, goalies_present = {}, set()
        for team in on_ice:
            team_id = str(team.get("teamId", ""))
            ids = {str(entry.get("athleteid", "")) for entry in team.get("entries", [])}
            if ids & goalie_ids:
                goalies_present.add(team_id)
            skaters[team_id] = len(ids - goalie_ids)
        # Both goalies must be present; this avoids mislabeling an empty-net
        # 6-on-5 as a power play. Unequal active skaters identify the PP side.
        game_status = competition.get("status") or {}
        in_intermission = (game_status.get("displayClock") == "20:00"
                           and game_status.get("displayPeriod"))
        last_play = plays[-1] if plays else {}
        if (not in_intermission and (last_play.get("type") or {}).get("text") != "Period End"
                and len(skaters) == 2 and len(goalies_present) == 2
                and max(skaters.values()) <= 5):
            sides = sorted(skaters.items(), key=lambda item: item[1])
            if sides[1][1] == sides[0][1]:
                power_play = "No active power play"
            elif sides[1][1] > sides[0][1]:
                power_play = teams.get(sides[1][0], "")
        last_goal = ""
        if goals:
            latest = next((play for play in reversed(plays) if play.get("scoringPlay")), {})
            text = str(latest.get("text", "")).strip()
            scorer = text.split(" Goal", 1)[0].strip() or text
            when = " ".join(part for part in (
                (latest.get("period") or {}).get("displayValue", ""),
                (latest.get("clock") or {}).get("displayValue", "")) if part)
            team = teams.get(str((latest.get("team") or {}).get("id", "")), "")
            last_goal = " · ".join(part for part in (when, team, scorer) if part)
        return {"scoreDetails": goals[-12:], "lastGoal": last_goal,
                "powerPlay": power_play}

    def _date_urls(self, now):
        first = now - timedelta(days=self.lookback_days)
        count = min(self.max_dates, self.lookback_days + self.lookahead_days + 1)
        return [
            "https://site.api.espn.com/apis/site/v2/sports/"
            + self.sport_path + "/scoreboard?" + urlencode({"limit": 100, "dates":
                                                               (first + timedelta(days=offset)).strftime("%Y%m%d")})
            for offset in range(count)
        ]

    def _get_json(self, url):
        if type(self.client) is not HttpClient:
            return self.client.json(url, timeout=8)
        raw = subprocess.check_output(["curl", "-fsS", "--max-time", "8",
                                       "-H", "Accept: application/json", url],
                                      timeout=10)
        return json.loads(raw)

    def fetch(self):
        from datetime import datetime, timezone

        now = datetime.fromtimestamp(self.clock(), timezone.utc)
        urls = self._date_urls(now)
        events, seen, failed_dates = [], set(), []
        for url in urls:
            date = url.rsplit("dates=", 1)[-1]
            try:
                payload = self._get_json(url)
            except Exception:
                failed_dates.append(date)
                continue
            for event in payload.get("events", []):
                event_id = str(event.get("id", "")).strip()
                # ESPN events have IDs. The fallback prevents duplicate rows
                # from malformed fixtures without inventing a second entity.
                key = event_id or json.dumps(event, sort_keys=True, separators=(",", ":"))
                if key not in seen:
                    seen.add(key)
                    events.append(event)
        if len(failed_dates) == len(urls):
            raise RuntimeError("NHL schedule failed for every requested date")
        # Scoreboard data omits the goal log. Keep this enrichment optional so
        # a play-by-play outage never takes down schedules or score reporting.
        followed_teams = {str(team).upper() for team in self.config.get("teams", ["TOR"])}
        for event in events:
            event_id = str(event.get("id", "")).strip()
            competitors = ((event.get("competitions") or [{}])[0].get("competitors") or [])
            has_followed_team = any(
                str((side.get("team") or {}).get("abbreviation", "")).upper() in followed_teams
                for side in competitors)
            if not event_id or _state(event) != "in" or not has_followed_team:
                continue
            try:
                event["_marqueeScoreDetails"] = self._score_details(
                    self._get_json(self._summary_url(event_id)))
            except Exception:
                event["_marqueeScoreDetails"] = {}
        events.sort(key=lambda event: (event.get("date") or "", str(event.get("id", ""))))
        return {"events": events, "_fetch": {
            "requestedDates": len(urls), "successfulDates": len(urls) - len(failed_dates),
            "failedDates": failed_dates}}

    def health_details(self, payload):
        details = payload.get("_fetch") or {}
        failed = details.get("failedDates") or []
        if not failed:
            return {}
        requested = details.get("requestedDates", len(failed))
        succeeded = details.get("successfulDates", max(0, requested - len(failed)))
        message = (f"NHL schedule partially fetched: {succeeded}/{requested} dates succeeded; "
                   f"failed dates: {', '.join(failed)}")
        return {"state": "degraded", "error": message, "errorSummary": message,
                "reason": "NHL schedule partially fetched", "lastSuccessReason": message}

    def _contexts(self, payload, now, browse=False):
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
            if (not browse and lifecycle == EventState.UPCOMING
                    and starts - now > timedelta(hours=24)):
                continue
            if browse and lifecycle in (EventState.POST_EVENT, EventState.RESULT):
                continue
            opponent = next((x for x in competitors if x is not followed), {})
            status = (((event.get("status") or {}).get("type") or {}).get("shortDetail", ""))
            broadcasts = []
            for broadcast in competition.get("broadcasts") or []:
                broadcasts.extend(str(name).strip() for name in broadcast.get("names", [])
                                  if str(name).strip())
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
                                        "status": status,
                                        "broadcast": ", ".join(dict.fromkeys(broadcasts)),
                                        **(event.get("_marqueeScoreDetails") or {})}))
        return values

    def contexts(self, payload, now):
        return self._contexts(payload, now)

    def browse_contexts(self, payload, now):
        return self._contexts(payload, now, browse=True)


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
    lookahead_days = 30

    def _contexts(self, payload, now, browse=False):
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
            if (not browse and lifecycle == EventState.UPCOMING
                    and starts - now > timedelta(hours=24)):
                continue
            if browse and lifecycle in (EventState.POST_EVENT, EventState.RESULT):
                continue
            fights = event.get("competitions") or []
            active = next((fight for fight in fights if _state(fight) == "in"), None)
            current = active or (fights[-1] if fights else {})
            sides = current.get("competitors") or []
            completed = [fight for fight in fights if _state(fight) == "post"]
            rows = (["LAST · " + _result(fight) for fight in reversed(completed[-2:])]
                    if lifecycle in (EventState.LIVE, EventState.POST_EVENT) else
                    ["CARD · " + _fight_label(fight) for fight in reversed(fights[-2:])])
            odds_data = current.get("odds") or event.get("odds") or []
            odds = odds_data if isinstance(odds_data, dict) else next(
                (item for item in odds_data if isinstance(item, dict)), {})
            odds_text = str(odds.get("details") or "").strip() if isinstance(odds, dict) else ""
            over_under = str(odds.get("overUnder") or "").strip() if isinstance(odds, dict) else ""
            if odds_text:
                rows.append("ODDS · " + odds_text + (" · O/U " + over_under if over_under else ""))
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

    def contexts(self, payload, now):
        return self._contexts(payload, now)

    def browse_contexts(self, payload, now):
        return self._contexts(payload, now, browse=True)


class UFCProvider(MMAProvider):
    name = "ufc"
    sport_path = "mma/ufc"
    reason = "ESPN UFC cards, fights and completed-bout results"


class PFLProvider(MMAProvider):
    name = "pfl"
    sport_path = "mma/pfl"
    reason = "ESPN PFL cards and live bouts; UFC wins overlapping events"
    accent = "#d4a62c"
