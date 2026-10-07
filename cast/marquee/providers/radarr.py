"""Upcoming movie releases from the household's Radarr calendar."""
import urllib.parse
from datetime import datetime, timedelta, timezone

from .model import Context, EventState, parse_time
from .provider import Provider
from .sonarr import placeholder


class RadarrProvider(Provider):
    name = "movies"
    refresh_seconds = 900
    stale_seconds = 7200

    def fetch(self):
        base = self.config.get("url", "").rstrip("/")
        key = self.config.get("api_key", "")
        if not base or not key:
            raise ValueError("RADARR_URL / RADARR_API_KEY not configured")
        now = self.config.get("_now") or datetime.now(timezone.utc)
        days = int(self.config.get("lookahead_days", 90))
        query = urllib.parse.urlencode({"start": (now - timedelta(days=1)).date().isoformat(),
                                        "end": (now + timedelta(days=days)).date().isoformat(),
                                        "includeMovie": "true"})
        return self.client.json(base + "/api/v3/calendar?" + query,
                                {"X-Api-Key": key})

    def contexts(self, payload, now):
        self.config["_now"] = now
        days = int(self.config.get("lookahead_days", 90))
        contexts, rejected = [], 0
        for movie in payload if isinstance(payload, list) else []:
            title = str(movie.get("title") or "").strip()
            if placeholder(title):
                rejected += 1
                continue
            release = parse_time(movie.get("digitalRelease") or movie.get("physicalRelease")
                                 or movie.get("inCinemas") or movie.get("releaseDate"))
            if not release or not now - timedelta(hours=24) <= release <= now + timedelta(days=days):
                rejected += 1
                continue
            delta = (release - now).total_seconds()
            has_file = bool(movie.get("hasFile"))
            state = (EventState.POST_EVENT if has_file or delta < -3600 else
                     EventState.LIVE if delta <= 0 else
                     EventState.STARTING_SOON if delta <= 6 * 3600 else EventState.UPCOMING)
            if state == EventState.POST_EVENT:
                rejected += 1
                continue
            images = movie.get("images") or []
            image = next((item.get("remoteUrl", "") for item in images
                          if item.get("coverType") in ("fanart", "poster")), "")
            tmdb_id = movie.get("tmdbId")
            contexts.append(Context(
                id=f"radarr:{movie.get('id')}", provider=self.name, type="movie_release",
                subtype="movie", title=title,
                subtitle=str(movie.get("year") or ""),
                body="Available now" if has_file else "Upcoming movie release",
                start_time=release, event_state=state,
                priority=int(self.config.get("priority", 55)), relevance=85,
                urgency=85 if abs(delta) < 6 * 3600 else 55, significance=60,
                expires_at=release + timedelta(days=1),
                refresh_after=now + timedelta(minutes=15),
                artwork_url=image, background_url=image, icon="mdi:movie-open",
                accent="#f59e0b",
                source_url=f"https://www.themoviedb.org/movie/{tmdb_id}" if tmdb_id else "",
                targets=["kiosk"], stats=["Monitored in Radarr"],
                raw={"hasFile": has_file}))
        self.reason = (f"{len(payload) if isinstance(payload, list) else 0} releases; "
                       f"{rejected} filtered; {len(contexts)} relevant")
        return contexts
