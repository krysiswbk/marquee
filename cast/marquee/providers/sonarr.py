import urllib.parse
import re
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .model import Context, EventState, parse_time
from .provider import Provider


TBA = re.compile(r"^(?:tba|tbd|unknown|untitled|to be (?:announced|determined))$", re.I)


def placeholder(value):
    """True only for placeholder titles, not legitimate titles containing the letters TBA."""
    text = str(value or "").strip()
    text = re.sub(r"^[\[(]|[\])]$", "", text).strip()
    return not text or bool(TBA.fullmatch(text))


class SonarrProvider(Provider):
    name = "tv"
    refresh_seconds = 900
    stale_seconds = 7200

    def fetch(self):
        base = self.config.get("url", "").rstrip("/")
        key = self.config.get("api_key", "")
        if not base or not key:
            raise ValueError("SONARR_URL / SONARR_API_KEY not configured")
        now = self.config.get("_now") or datetime.now(timezone.utc)
        hours = int(self.config.get("lookahead_hours", 24))
        start, end = now - timedelta(days=1), now + timedelta(hours=hours)
        query = urllib.parse.urlencode({"start": start.date().isoformat(),
                                        "end": end.date().isoformat(),
                                        "includeSeries": "true"})
        return self.client.json(base + "/api/v3/calendar?" + query,
                                {"X-Api-Key": key})

    def contexts(self, payload, now):
        self.config["_now"] = now
        zone = ZoneInfo(self.config.get("timezone", "America/Toronto"))
        tracked = {x.lower() for x in self.config.get("tracked_shows", [])}
        tracking_mode = self.config.get("tracking_mode", "show_all")
        contexts, rejected = [], 0
        for episode in payload if isinstance(payload, list) else []:
            series = episode.get("series") or {}
            title = series.get("title", "")
            episode_title = episode.get("title", "")
            if (not series.get("monitored", True) or placeholder(title) or
                    placeholder(episode_title) or
                    (tracking_mode == "tracked_only" and title.lower() not in tracked) or
                    (tracking_mode == "show_all" and tracked and title.lower() not in tracked)):
                rejected += 1; continue
            air = parse_time(episode.get("airDateUtc"))
            hours = int(self.config.get("lookahead_hours", 24))
            if not air or not now - timedelta(hours=24) <= air <= now + timedelta(hours=hours):
                rejected += 1; continue
            delta = (air - now).total_seconds()
            has_file = bool(episode.get("hasFile"))
            state = (EventState.POST_EVENT if has_file or delta < -3600 else
                     EventState.LIVE if delta <= 0 else
                     EventState.STARTING_SOON if delta <= 6*3600 else EventState.UPCOMING)
            if state == EventState.POST_EVENT:
                rejected += 1; continue
            subtype = "season_premiere" if episode.get("episodeNumber") == 1 else "episode"
            priority = 63 if has_file else (58 if state == EventState.STARTING_SOON else 50)
            image = next((x.get("remoteUrl", "") for x in series.get("images", [])
                          if x.get("coverType") in ("fanart", "poster")), "")
            contexts.append(Context(
                id=f"sonarr:{episode.get('id')}", provider=self.name, type="tv_release",
                subtype=subtype, title=title,
                subtitle=f"S{episode.get('seasonNumber', 0):02}E{episode.get('episodeNumber', 0):02} · {episode_title}",
                body="Available now" if has_file else ("Airs tonight" if air.astimezone(zone).date()
                     == now.astimezone(zone).date() else "Upcoming tracked episode"),
                start_time=air, event_state=state, priority=priority, relevance=90,
                urgency=85 if abs(delta) < 6*3600 else 55,
                significance=80 if subtype == "season_premiere" else 55,
                expires_at=air + timedelta(hours=24), refresh_after=now + timedelta(minutes=15),
                artwork_url=image, background_url=image, icon="mdi:television-classic",
                accent="#a855f7", source_url=series.get("tvdbId") and
                f"https://thetvdb.com/?tab=series&id={series['tvdbId']}" or "",
                targets=(["kiosk", "hubs"] if state in
                         (EventState.STARTING_SOON, EventState.LIVE,
                          EventState.POST_EVENT) else ["kiosk"]),
                stats=["Monitored in Sonarr"], raw={"hasFile": has_file}))
        self.reason = f"{len(payload) if isinstance(payload, list) else 0} releases; {rejected} filtered; {len(contexts)} relevant"
        return contexts
