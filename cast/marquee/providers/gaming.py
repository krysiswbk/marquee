"""Gaming signals: claimed free games and curated HA game-release calendars."""
import json
import os
import re
import unicodedata
import urllib.parse
from datetime import datetime, time, timedelta, timezone
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from .model import Context, EventState, parse_time
from .provider import Provider, atomic_json


def store_title(title):
    """Calendar labels may add a platform list that is not part of the name."""
    return re.sub(r"\s*\((?=[^)]*(?:PS[45]|Xbox|Switch|PC))[^)]*\)\s*$", "", title, flags=re.I).strip()


def title_key(title):
    folded = unicodedata.normalize("NFKD", title).casefold()
    return re.sub(r"[^a-z0-9]+", " ", "".join(c for c in folded if not unicodedata.combining(c))).strip()


def steam_image(value):
    """Only accept HTTPS artwork from Steam's own image hosts."""
    if not isinstance(value, str):
        return ""
    parts = urlsplit(value)
    host = parts.hostname or ""
    return value if parts.scheme == "https" and host.endswith(".steamstatic.com") else ""


class GamingProvider(Provider):
    name = "gaming"
    refresh_seconds = 600
    stale_seconds = 7200

    def release_artwork(self, title):
        search = "https://store.steampowered.com/api/storesearch/?" + urllib.parse.urlencode(
            {"term": store_title(title), "l": "en", "cc": "ca"})
        matches = self.client.json(search, timeout=4).get("items", [])
        expected = title_key(store_title(title))
        exact = next((item for item in matches if title_key(str(item.get("name", ""))) == expected), None)
        if not exact or not str(exact.get("id", "")).isdigit():
            return {"artwork": "", "background": ""}
        app_id = str(exact["id"])
        detail_url = "https://store.steampowered.com/api/appdetails?" + urllib.parse.urlencode(
            {"appids": app_id, "cc": "ca", "l": "en"})
        detail = self.client.json(detail_url, timeout=4).get(app_id, {})
        data = detail.get("data", {}) if detail.get("success") else {}
        if title_key(str(data.get("name", ""))) != expected:
            return {"artwork": "", "background": ""}
        return {"artwork": steam_image(data.get("header_image")),
                "background": steam_image(data.get("background_raw"))}

    def enrich_releases(self, releases):
        """Cache exact matches; a failed lookup must never suppress a release."""
        path = os.path.join(self.data_dir, "provider-cache", "gaming-artwork.json")
        try:
            with open(path, encoding="utf-8") as handle:
                cache = json.load(handle)
            if not isinstance(cache, dict):
                cache = {}
        except (OSError, ValueError, TypeError):
            cache = {}
        now = self.clock()
        limit = max(0, min(10, int(self.config.get("max_releases", 3))))
        seen = set()
        matched = 0
        for item in sorted((event for event in releases if isinstance(event, dict)),
                           key=lambda event: str(event.get("start", ""))):
            title = str(item.get("summary") or "").strip()
            if not title:
                continue
            key = title_key(store_title(title))
            if not key or key in seen:
                continue
            seen.add(key)
            if matched >= limit:
                break
            matched += 1
            if item.get("artwork"):
                continue
            cached = cache.get(key, {})
            try:
                age = now - float(cached.get("at", 0)) if isinstance(cached, dict) else float("inf")
            except (ValueError, TypeError):
                age = float("inf")
            image = cached if 0 <= age < (86400 * 30 if cached.get("artwork") else 21600) else None
            if image is None:
                try:
                    image = self.release_artwork(title)
                except (OSError, ValueError, TypeError, KeyError):
                    continue
                cache[key] = {"at": now, **image}
            item["artwork"] = steam_image(image.get("artwork"))
            item["background"] = steam_image(image.get("background"))
        try:
            atomic_json(path, cache)
        except OSError:
            pass

    def fetch(self):
        payload = {"claims": [], "releases": []}
        claims_url = str(self.config.get("claims_url", "")).strip()
        if claims_url:
            claims = self.client.json(claims_url, timeout=8)
            payload["claims"] = claims.get("claims", [])

        # AppDaemon writes only allowlisted game-release calendars through the
        # Marquee HTTP API. Keeping this local avoids HA credentials and a
        # third-party release API in the Marquee container.
        try:
            with open(os.path.join(self.data_dir, "ha-gaming-releases.json")) as handle:
                release_feed = json.load(handle)
            if self.clock() - float(release_feed.get("updated", 0)) <= 7200:
                payload["releases"] = release_feed.get("events", [])
        except (OSError, ValueError, TypeError):
            pass

        if isinstance(payload["releases"], list):
            self.enrich_releases(payload["releases"])

        return payload

    def contexts(self, payload, now):
        household_zone = ZoneInfo(self.config.get("timezone", "UTC"))
        today = now.astimezone(household_zone).date()
        midnight = datetime.combine(today + timedelta(days=1), time.min, household_zone)
        contexts = []
        seen_claims = set()
        claim_contexts = []
        for item in (payload.get("claims", []) if isinstance(payload, dict) else []):
            claimed_at = parse_time(item.get("claimed_at"))
            if claimed_at is not None and claimed_at.tzinfo is None:
                claimed_at = claimed_at.replace(tzinfo=timezone.utc)
            title = str(item.get("title", "")).strip()
            store = str(item.get("store", "Free game")).strip()
            if (not title or not claimed_at or claimed_at > now or
                    claimed_at.astimezone(household_zone).date() != today):
                continue
            identity = (store.casefold(), title.casefold())
            if identity in seen_claims:
                continue
            seen_claims.add(identity)
            claim_contexts.append(Context(
                id=f"gaming:claimed:{item.get('id', title)}",
                provider=self.name,
                type="gaming",
                subtype="free_game_claimed",
                title=title,
                subtitle=f"Claimed free on {store}",
                body=f"Added to the {store} library.",
                start_time=claimed_at,
                # A library acquisition is not an event recap. RESULT keeps it
                # out of the globally suppressed POST_EVENT lifecycle while
                # the explicit card status supplies natural viewer copy.
                event_state=EventState.RESULT,
                priority=int(self.config.get("priority", 45)),
                relevance=65,
                urgency=25,
                freshness=max(25, 100 - int((now - claimed_at).total_seconds() / 86400) * 12),
                significance=40,
                artwork_url=str(item.get("artwork", "")),
                background_url=str(item.get("artwork", "")),
                icon="gamepad-variant",
                accent="#8b5cf6",
                expires_at=midnight,
                source_url=str(item.get("url", "")),
                targets=["kiosk"],
                stats=[f"Grabbed {claimed_at.astimezone(household_zone).strftime('%a %b %-d, %-I:%M %p')}"],
                raw={"status": "Claimed"}
            ))
        claim_contexts.sort(key=lambda context: context.start_time, reverse=True)
        contexts.extend(claim_contexts[:int(self.config.get("max_claims", 3))])
        release_contexts = []
        lookahead = now + timedelta(days=int(self.config.get("release_lookahead_days", 30)))
        seen_releases = set()
        for item in payload.get("releases", []):
            title = str(item.get("summary", "")).strip()
            starts = parse_time(item.get("start"))
            ends = parse_time(item.get("end"))
            if not title or not starts or starts < now - timedelta(hours=12) or starts > lookahead:
                continue
            identity = (title.casefold(), starts.date())
            if identity in seen_releases:
                continue
            seen_releases.add(identity)
            days = max(0, (starts.astimezone().date() - now.astimezone().date()).days)
            when = "Today" if days == 0 else "Tomorrow" if days == 1 else starts.astimezone().strftime("%a, %b %-d")
            release_contexts.append(Context(
                id=f"gaming:release:{item.get('id') or title}:{starts.isoformat()}",
                provider=self.name, type="gaming", subtype="game_release",
                title=title, subtitle=f"Game release · {when}",
                body=str(item.get("description", "")).strip()[:240],
                start_time=starts, end_time=ends, event_state=EventState.UPCOMING,
                priority=int(self.config.get("release_priority", self.config.get("priority", 45))),
                relevance=70 if days <= 7 else 55, urgency=70 if days <= 1 else 40,
                freshness=75, significance=50, icon="calendar-star", accent="#8b5cf6",
                artwork_url=str(item.get("artwork") or ""),
                background_url=str(item.get("background") or item.get("artwork") or ""),
                expires_at=ends or starts + timedelta(days=1),
                source_url=str(item.get("url", "")),
                targets=["kiosk"], stats=[when]))
        release_contexts.sort(key=lambda context: context.start_time)
        contexts.extend(release_contexts[:int(self.config.get("max_releases", 3))])
        return sorted(contexts, key=lambda context: context.start_time, reverse=True)
