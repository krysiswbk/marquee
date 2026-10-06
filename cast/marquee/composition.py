#!/usr/bin/env python3
"""Marquee — a "now playing" marquee for Google Nest Hubs.
The whole app in one container: front end + back end.

Backend: polls the media server every POLL_SECONDS; while something plays it
downloads poster/backdrop/logo, writes now-playing.json, and casts the card to
the Hub; when idle it releases the Hub.

The media server is chosen on the settings page or by env (settings win,
env is the container default, plex when neither says otherwise):
  MEDIA_BACKEND=plex|emby|jellyfin -> get_session() -> current_session() /
  emby_current_session() (jellyfin shares the emby path — API-compatible fork)
Each backend's host and API key/token can also be entered on the settings
page (one host + key field pair, pointed at the backend the dropdown picks);
secrets are stored server-side and never served back to a browser.

Frontend (one HTTP server on :8084): serves the card page and art from
output/, the settings UI at /settings, /save, and /release-notes.

Env knobs: PAGE_URL, POLL_SECONDS, REPO_DIR, SERVE_PORT, DATA_DIR.
  Plex:     PLEX_HOST, PLEX_TOKEN
  Emby:     EMBY_HOST, EMBY_API_KEY
  Jellyfin: JELLYFIN_HOST, JELLYFIN_API_KEY (or the EMBY_ pair; shared backend)
Optional TMDB_API_KEY enables the credits-scene badge; optional PLEX_USERS /
PLEX_DEVICES limit which users and player devices trigger the marquee (also
editable live on the settings page); both backends honor both filters.
Optional BLOCK_TAGS lists do-not-cast words: a session whose genres or tags
contain one is never cast, so the marquee cannot overshare. The
cast device comes from the settings page (auto-discovered via catt scan) or
the HUB_IP env fallback.
"""
from .attention.briefing import supporting

import json
import mimetypes
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
import socket
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from marquee.providers import ContextEngine
from marquee.providers.registry import create_providers, load_provider_config
from marquee.config import ConfigRepository
from marquee.core.arbitration import ContextArbiter
from marquee.core.cast_ambient import calendar_agenda
from marquee.core.events import EventBus
from marquee.services.screen_testing import SAMPLES, forced_context, sample_catalog

from marquee import __version__

VERSION = __version__
HUB_IP = os.environ.get("HUB_IP", "")
GARAGE_HUB_IP = os.environ.get("GARAGE_HUB_IP", "")
BEDROOM_HUB_IP = os.environ.get("BEDROOM_HUB_IP", "10.10.3.81")
PRESENCE_TARGETS = {
    "10.10.3.73": "living_room",
    "10.10.3.74": "garage",
    "10.10.3.81": "bedroom",
}
PAGE_URL = os.environ.get("PAGE_URL", "")
PLEX = os.environ.get("PLEX_HOST", "").rstrip("/")
TOKEN = os.environ.get("PLEX_TOKEN", "")
POLL = int(os.environ.get("POLL_SECONDS", "5"))
REPO = os.environ.get("REPO_DIR", "/repo")
TMDB_KEY = os.environ.get("TMDB_API_KEY", "")
SERVE_PORT = int(os.environ.get("SERVE_PORT", "8084"))
CAST_MUTE_SETTLE = float(os.environ.get("CAST_MUTE_SETTLE_SECONDS", "0.8"))
CAST_UNMUTE_DELAY = float(os.environ.get("CAST_UNMUTE_DELAY_SECONDS", "2.5"))
def csv_set(value):
    return {v.strip().lower() for v in (value or "").split(",") if v.strip()}


# Comma-separated Plex usernames/device names that may trigger the marquee;
# empty = everyone / any device. The env var is the container-level default:
# whatever is typed on the settings page replaces it, exactly as HUB_IP
# behaves. The raw strings are kept so the settings page can show them as
# placeholders — an env filter nobody can see is an env filter that lies.
ENV_USERS = os.environ.get("PLEX_USERS", "")
ENV_DEVICES = os.environ.get("PLEX_DEVICES", "")
USERS = csv_set(ENV_USERS)
DEVICES = csv_set(ENV_DEVICES)


def filter_set(saved, env_default):
    """The allow-list actually in force: what the settings page says, or the
    container's env default when that field is blank.

    Overrides rather than merges. A union would let an env var filter sessions
    that the settings page shows no sign of, and could never be lifted from the
    UI — clearing the field would change nothing.
    """
    chosen = csv_set(saved)
    return chosen if chosen else csv_set(env_default)


# Comma-separated do-not-cast words: a session whose genres or tags contain
# one of these is never cast, so the marquee cannot overshare. Same
# default-vs-override rule as the other filters.
ENV_BLOCK_TAGS = os.environ.get("BLOCK_TAGS", "")


def content_blocked(words, terms):
    """True when any do-not-cast word matches any of the item's genre / tag /
    content-rating terms, case-insensitive. A word of 3+ characters matches
    *inside* a term ("adult" blocks "Adult Animation") — for an overshare
    guard, blocking too much beats leaking. Shorter words must equal the
    whole term, so blocking the "R" rating does not block "Horror". Empty
    words block nothing."""
    lowered = [t.lower() for t in terms if t]
    return any(w == t or (len(w) >= 3 and w in t)
               for w in words for t in lowered)


def plex_item_terms(video):
    """Genre, Label, and content-rating terms on a Plex session Video."""
    return ([g.get("tag") or "" for g in video.findall("Genre")]
            + [l.get("tag") or "" for l in video.findall("Label")]
            + [video.get("contentRating") or ""])


def emby_item_terms(item):
    """Genre, tag, and content-rating terms on an Emby/Jellyfin
    NowPlayingItem. OfficialRating is in the enrich field list, so the
    post-enrich re-check sees it even when /Sessions omits it."""
    return ((item.get("Genres") or [])
            + [t.get("Name") or "" for t in (item.get("TagItems") or [])]
            + (item.get("Tags") or [])
            + [item.get("OfficialRating") or ""])


# Only these env vars are ever shown to the settings page. An allowlist, not a
# denylist: a future PLEX_TOKEN-shaped variable must not leak by default.
ENV_HINT_KEYS = ("hubIp", "plexUsers", "plexDevices", "blockTags")


def env_defaults():
    """Container-level defaults the settings page shows as placeholders, so a
    blank field reads as "inheriting this" instead of "nothing is set"."""
    return {"hubIp": HUB_IP, "plexUsers": ENV_USERS,
            "plexDevices": ENV_DEVICES, "blockTags": ENV_BLOCK_TAGS}

BACKENDS = ("plex", "emby", "jellyfin")
# MEDIA_BACKEND is the container-level default; the settings-page dropdown
# overrides it without a restart. Empty or unknown means plex.
ENV_BACKEND = os.environ.get("MEDIA_BACKEND", "").lower()
if ENV_BACKEND not in BACKENDS:
    ENV_BACKEND = "plex"


def uses_emby_backend(backend):
    """Jellyfin forked from Emby; the /Sessions, /Items and image APIs this app
    uses are identical (verified against Jellyfin 10.11), so both share the Emby
    session path and the same env-var seam."""
    return backend in ("emby", "jellyfin")


def media_backend(settings=None):
    """Backend picked in settings wins; MEDIA_BACKEND env is the fallback —
    the same rule hub_ip() follows. Resolved per poll, so a *saved* change
    applies on the next poll without a restart."""
    s = settings if settings is not None else load_settings()
    chosen = (s.get("mediaBackend") or "").lower()
    return chosen if chosen in BACKENDS else ENV_BACKEND


def get_session():
    """Current now-playing dict from the configured backend, or None."""
    return (emby_current_session() if uses_emby_backend(media_backend())
            else current_session())

OUTPUT = os.path.join(REPO, "output")
JSON_PATH = os.path.join(OUTPUT, "now-playing.json")
DATA_DIR = os.environ.get("DATA_DIR", OUTPUT)
SETTINGS_PATH = os.path.join(DATA_DIR, "settings.json")
LIVE_SETTINGS_PATH = os.path.join(DATA_DIR, "live-settings.json")
AMBIENT_PATH = os.path.join(DATA_DIR, "ambient.json")
HA_WEATHER_PATH = os.path.join(DATA_DIR, "ha-weather.json")
CUSTOM_BACKDROP_PATH = os.path.join(DATA_DIR, "custom-backdrop.img")
MAX_CUSTOM_BACKDROP_BYTES = 15 * 1024 * 1024

# Contexts are deliberately provider-neutral.  Built-in sports providers and
# external publishers both produce this shape; the display only sees the
# highest-priority unexpired item.  Keeping this seam here prevents Plex, UFC,
# NHL, Music Assistant, etc. from growing display-specific branches.
CONTEXT_PATH = os.path.join(DATA_DIR, "media-contexts.json")
CONTEXT_LOCK = threading.Lock()
SPORTS_REFRESH_SECONDS = 60
SPORTS_CACHE = {"at": 0.0, "contexts": []}
CURRENT_PLEX = {"info": None}
PROVIDER_ENGINE = {"value": None}
CONFIG_REPOSITORY = ConfigRepository(DATA_DIR)
EVENT_BUS = EventBus()
ARBITER = ContextArbiter(EVENT_BUS)
KIOSK_ACTIVITY = {"last": 0.0, "source": ""}


def kiosk_interacting(now=None):
    """Kiosk-only activity gate; Cast selection never consults this state."""
    now = time.time() if now is None else now
    timeout = CONFIG_REPOSITORY.effective()["display"]["kiosk_interaction_idle_seconds"]
    return bool(KIOSK_ACTIVITY["last"] and now - KIOSK_ACTIVITY["last"] < timeout)


def iso_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def clean_context(value, source="external"):
    """Validate the small public context contract and discard unsafe fields."""
    if not isinstance(value, dict) or not str(value.get("id", "")).strip():
        raise ValueError("context id is required")
    expires = iso_time(value.get("expires"))
    if not expires:
        raise ValueError("expires must be an ISO-8601 timestamp")
    def text_value(name, limit=300):
        v = value.get(name)
        return str(v).strip()[:limit] if v is not None else ""
    result = {
        "id": text_value("id", 100), "source": text_value("source", 40) or source,
        "priority": max(0, min(100, int(value.get("priority", 0)))),
        "type": text_value("type", 40),
        "eventState": text_value("eventState", 40) or text_value("event_state", 40), "title": text_value("title", 160),
        "subtitle": text_value("subtitle", 200), "primary": text_value("primary", 80),
        "secondary": text_value("secondary", 80), "detail": text_value("detail", 400),
        "status": text_value("status", 60), "accent": text_value("accent", 20),
        "starts": text_value("starts", 40), "expires": expires.astimezone(timezone.utc).isoformat(),
        "artwork": text_value("artwork", 500),
        "background": text_value("background", 500),
        "icon": text_value("icon", 500),
    }
    targets = value.get("targets") or ["kiosk", "hubs"]
    result["targets"] = [x for x in targets if x in ("kiosk", "hubs")]
    if not result["targets"]:
        raise ValueError("targets must include kiosk and/or hubs")
    for name in ("left", "right"):
        side = value.get(name) or {}
        if isinstance(side, dict):
            result[name] = {k: ("" if side.get(k) is None else str(side.get(k))).strip()[:200]
                            for k in ("name", "abbr", "score", "record", "logo")}
    rows = value.get("rows") or []
    result["rows"] = [str(row).strip()[:180] for row in rows[:5] if str(row).strip()]
    return result


def saved_contexts(now=None):
    now = now or datetime.now(timezone.utc)
    try:
        with open(CONTEXT_PATH) as f:
            values = json.load(f)
    except (OSError, ValueError):
        values = []
    return [c for c in values if iso_time(c.get("expires")) and iso_time(c["expires"]) > now]


def save_context(context):
    with CONTEXT_LOCK:
        current = saved_contexts()
        previous = next((c for c in current if c.get("id") == context["id"]), None)
        if str(context.get("type", "")).endswith("_post"):
            same_result = previous and previous.get("type") == context.get("type")
            context["observedAt"] = (previous.get("observedAt") if same_result else None) \
                or datetime.now(timezone.utc).isoformat()
        values = [c for c in current if c.get("id") != context["id"]]
        values.append(context)
        atomic_write(CONTEXT_PATH, json.dumps(values))


def delete_contexts(prefix="screen-test:"):
    """Remove temporary/admin contexts while leaving provider publications alone."""
    with CONTEXT_LOCK:
        current = saved_contexts()
        values = [c for c in current if not str(c.get("id", "")).startswith(prefix)]
        atomic_write(CONTEXT_PATH, json.dumps(values))
        return len(current) - len(values)


ATTENTION = {"value": None}


def cast_kiosk_enabled(display="hubs"):
    """Explicit opt-in for each configured Cast destination; off for old profiles."""
    key = {"hubs": "castKioskActivity", "garage": "garageKioskActivity"}.get(display)
    return bool(key and load_settings().get(key) is True)


def best_context(plex_info=None, display="hubs"):
    attention = ATTENTION.get("value")
    family = attention.family(display) if attention else display
    kiosk_receiver = cast_kiosk_enabled(display)
    if kiosk_receiver:
        family = "kiosk"
    interacting = family == "kiosk" and not kiosk_receiver and kiosk_interacting()
    saved = saved_contexts()
    engine = PROVIDER_ENGINE["value"]
    modular = []
    if engine:
        engine.tick()
        modular = [c.display_dict() for c in engine.all_contexts()]
    scene_saved = [c for c in saved if not supporting(c)] if family == "kiosk" else saved
    scene_modular = [c for c in modular if not supporting(c)] if family == "kiosk" else modular
    if family == "hubs" and not kiosk_receiver:
        agenda = calendar_agenda(scene_saved + scene_modular)
        if agenda:
            scene_modular = scene_modular + [agenda]
        try:
            winner = ARBITER.select(scene_saved, scene_modular, plex_info, family,
                                    ambient=True)
        except TypeError as error:
            # Keep the small arbitration seam compatible with test/extension
            # implementations that predate the optional ambient lane.
            if "ambient" not in str(error):
                raise
            winner = ARBITER.select(scene_saved, scene_modular, plex_info, family)
    else:
        winner = ARBITER.select(scene_saved, scene_modular, plex_info, family)
    if attention:
        attention.sync_contexts(saved + modular, plex_info)
        important = attention.choose(display, winner, interacting)
        if important:
            # Household attention brings the desk forward; critical alarms still take over.
            if (family == "kiosk" and important.get("context", {}).get("type") == "household_attention"
                    and important.get("attention", {}).get("urgency") != "CRITICAL"):
                return {"playing": False, "householdFocus": important}
            return important
        registered = attention.manager.displays.get(display)
        if registered is None or not registered.available or not registered.user_visible:
            return None
    if interacting:
        return None
    if not winner:
        # Cast receivers are released when neither playback nor an explicit
        # takeover needs them. Live/Kiosk renders its configured fallback.
        return None
    if winner.get("payload"):
        return winner["payload"]
    return {"playing": True, "ambient": family == "hubs" and not kiosk_receiver,
            "key": winner["id"], "type": "media_context",
            "context": winner, "title": winner.get("title", ""),
            "subtitle": winner.get("subtitle", ""), "summary": winner.get("detail", ""),
            "genres": [winner.get("source", "").upper()], "state": "playing",
            "backdrop": bool(winner.get("background") or winner.get("artwork")),
            "backgroundUrl": winner.get("background") or winner.get("artwork") or ""}


def image_mime(data):
    """Supported custom-backdrop type from magic bytes; None for anything else."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def radar_mime(data):
    """Radar additionally supports HA Environment Canada's animated GIF."""
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    return image_mime(data)


def custom_backdrop_info():
    """(path, MIME type, cache version) for the persisted custom image."""
    try:
        with open(CUSTOM_BACKDROP_PATH, "rb") as f:
            mime = image_mime(f.read(16))
        if not mime:
            return None
        stat = os.stat(CUSTOM_BACKDROP_PATH)
        return CUSTOM_BACKDROP_PATH, mime, str(stat.st_mtime_ns)
    except (OSError, ValueError):
        return None

THEMES = ("amber", "ice", "crimson", "emerald",
          "campaign", "concrete", "trophy", "bsides")
TEMPLATES = ("spotlight", "split", "hero", "lowerthird", "bigclock", "street",
             "fanart")
TITLE_FONTS = (
    "system", "bebas", "oswald", "playfair", "cinzel", "grotesk",
    "roboto", "montserrat", "lato", "raleway", "anton", "orbitron",
    "righteous", "merriweather", "libre", "bangers",
)
ACCENT_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
IP_RE = re.compile(r"^\d{1,3}(\.\d{1,3}){3}$")
DEFAULT_SETTINGS = {
    "hubIp": "",
    "castKioskActivity": False,
    "garageKioskActivity": False,
    "template": "spotlight",
    "theme": "amber",
    "accent": "",
    "titleFont": "system",
    "bodyFont": "system",
    "clockFormat": "12h",
    "clockSeconds": False,
    "showPlot": True, "showGenres": True, "showScores": True,
    "showMediaInfo": True, "showContentRating": True, "showRuntime": True,
    "showProgress": True, "showClock": True,
    "backdrop": True, "logo": True,
    "displayWidth": 1280, "displayHeight": 800,  # settings-preview target size (px)
    "sportsClockSize": 100, "sportsArtworkSize": 100,
    "sportsTextSize": 100, "sportsWeatherSize": 100,
    "liveVisibility": {},
    "liveLayout": {},
    "liveTheme": "studio",
    "showDeviceLocation": True,
    "streetRainAnimation": True,
    "customBackdropEnabled": False,
    "customBackdropFit": "cover",
    "customBackdropZoom": 100,
    "customBackdropX": 50,
    "customBackdropY": 50,
    "customBackdropOpacity": 35,
    "customBackdropBlur": 0,
    "customBackdropBrightness": 100,
    "plexUsers": "", "plexDevices": "",
    "blockTags": "",
    "rotateSeconds": 30,
    "showWeather": False, "weatherZip": "", "weatherUnits": "f",
    "weatherFX": True, "weatherIntensity": 2,
    "fanartKey": "", "fanartType": "background", "fanartRotateSeconds": 600,
    # {template: {block: {x,y,width,scale,align,font,color,panelBackground,panelBorder}}}
    "blockLayout": {},
    "presets": [],           # user-saved looks: {name, template, blockLayout, blockVisibility, metaOpts}
    "blockVisibility": {},  # {template: {block: bool}}, sparse — only overrides
    "mediaBackend": "",       # "" = inherit MEDIA_BACKEND env (plex when unset)
    "plexHost": "", "plexToken": "",
    "plexCleanPosters": True,
    "embyHost": "", "embyKey": "",
    "jellyfinHost": "", "jellyfinKey": "",
}

# Keys/tokens are write-only: stored in settings.json but never served back to
# a browser — /settings.json replaces each with a saved/not-saved hint.
SECRET_SETTINGS = ("plexToken", "embyKey", "jellyfinKey", "fanartKey")
# Connection/source settings belong to the application, not to a physical
# display profile. The Live editor inherits these from Cast but never stores a
# second copy of credentials in live-settings.json.
LIVE_SHARED_SETTINGS = (
    "hubIp", "castKioskActivity", "garageKioskActivity", "plexUsers", "plexDevices", "blockTags", "mediaBackend",
    "plexHost", "plexToken", "plexCleanPosters", "embyHost", "embyKey",
    "jellyfinHost", "jellyfinKey", "fanartKey", "weatherZip",
)


def served_settings(settings=None):
    """Settings as the browser may see them: each secret is swapped for a
    boolean <name>Set hint, so the page can say "saved" without knowing it.
    envBackend rides along so the page can show the container's default."""
    s = dict(settings if settings is not None else load_settings())
    for k in SECRET_SETTINGS:
        s[k + "Set"] = bool(s.pop(k, ""))
    s["envBackend"] = ENV_BACKEND
    custom = custom_backdrop_info()
    s["customBackdropAvailable"] = bool(custom)
    s["customBackdropVersion"] = custom[2] if custom else ""
    return s

EDITABLE_BLOCKS = ("clock", "weather", "category", "identity", "meta", "plot", "ratings",
                   "progress", "poster", "streetframe", "nowplaying",
                   "viewer", "device", "stream",
                   "activity", "tracks", "stinger")
# Blocks a user can freely add to or remove from a template. The credits badge
# remains content-driven, but its presence can now be disabled like any other
# Design block.
TOGGLEABLE_BLOCKS = ("clock", "weather", "category", "identity", "meta", "plot",
                     "ratings", "progress", "poster", "streetframe", "nowplaying",
                     "backdrop", "viewer",
                     "device", "stream", "activity", "tracks", "stinger")
# Each template's shipped block set, mirrored from the display:none rules in
# output/index.html. A user's blockVisibility only needs to store where they
# differ from this — the default itself never touches settings.json.
TEMPLATE_DEFAULT_BLOCKS = {
    "spotlight": ("backdrop", "clock", "category", "identity", "meta", "plot", "ratings", "progress", "poster", "stinger"),
    "split": ("backdrop", "clock", "category", "identity", "meta", "plot", "ratings", "progress", "poster", "stinger"),
    "hero": ("backdrop", "clock", "category", "identity", "meta", "ratings", "progress", "stinger"),
    "lowerthird": ("backdrop", "clock", "category", "identity", "meta", "ratings", "progress", "stinger"),
    "bigclock": ("backdrop", "clock", "identity", "progress"),
    "street": ("clock", "weather", "category", "identity", "meta", "plot", "ratings",
               "progress", "streetframe", "poster", "nowplaying", "device", "stream", "stinger"),
    # Fanart ships bare on purpose: the rotating art is the whole card until
    # the user adds blocks. Its art layer replaces backdrop (like street).
    "fanart": (),
}

# fanart.tv v3 art types, user-facing name -> (movie key, tv key).
from marquee.services import media as _media


def migrate_block_layout(value, current_template):
    """blockLayout used to be flat ({block: position}), applied to every
    template at once — nudging a block in Spotlight silently moved it in
    Street too. Nest it under the template the user was last on, so an
    upgrade doesn't change what they see; other templates start clean rather
    than inheriting a position nobody meant for them.

    ponytail: one-shot migration, no version flag. Once this has shipped for
    a while and old flat saves are gone, this can be deleted along with the
    isinstance branch that triggers it.
    """
    if not isinstance(value, dict):
        return {}
    if not value or any(k in TEMPLATES for k in value):
        return value  # already nested (or empty)
    return {current_template: value}


def clamp_setting(value, low, high, default):
    """Coerce value to an int within [low, high]; fall back to default on junk."""
    try:
        n = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return max(low, min(high, n))


def clean_display_settings(settings):
    """Clamp the settings-preview target display size to sane pixel bounds."""
    settings["displayWidth"] = clamp_setting(settings.get("displayWidth"), 320, 3840, 1280)
    settings["displayHeight"] = clamp_setting(settings.get("displayHeight"), 240, 2160, 800)
    settings["showDeviceLocation"] = bool(settings.get("showDeviceLocation"))
    settings["streetRainAnimation"] = bool(settings.get("streetRainAnimation"))
    for key in ("sportsClockSize", "sportsArtworkSize", "sportsTextSize",
                "sportsWeatherSize"):
        settings[key] = clamp_setting(settings.get(key), 60, 180, 100)
    return settings


LIVE_SURFACE_BLOCKS = {
    "sports": ("clock", "date", "weather", "event", "matchup", "status", "details", "rows"),
    "weather": ("clock", "conditions", "hours", "forecast", "radar", "headline", "details", "stats"),
    "media": ("clock", "weather", "source", "artwork", "title", "status", "details", "rows"),
    "home": ("greeting", "clock", "date", "weather", "house", "activity", "agenda"),
}


def clean_live_visibility(value):
    """Keep only documented surface/block boolean overrides."""
    if not isinstance(value, dict):
        return {}
    return {surface: {block: bool(blocks[block]) for block in allowed if block in blocks}
            for surface, allowed in LIVE_SURFACE_BLOCKS.items()
            if isinstance((blocks := value.get(surface)), dict)}


def clean_live_layout(value):
    """Independent per-surface positions for the Live/Kiosk renderer."""
    if not isinstance(value, dict):
        return {}
    return {surface: {block: clean_block_position(position)
                      for block, position in blocks.items()
                      if block in allowed and isinstance(position, dict)}
            for surface, allowed in LIVE_SURFACE_BLOCKS.items()
            if isinstance((blocks := value.get(surface)), dict)}


def _load_settings_file(path, fallback=None):
    try:
        with open(path) as f:
            saved = json.load(f)
        base = fallback if fallback is not None else DEFAULT_SETTINGS
        merged = {**DEFAULT_SETTINGS, **base,
                  **{k: v for k, v in saved.items() if k in DEFAULT_SETTINGS}}
        merged["blockLayout"] = migrate_block_layout(
            merged["blockLayout"], merged.get("template") or "spotlight")
        clean_custom_backdrop_settings(merged)
        clean_display_settings(merged)
        merged["liveVisibility"] = clean_live_visibility(merged.get("liveVisibility"))
        merged["liveLayout"] = clean_live_layout(merged.get("liveLayout"))
        return migrate_show_flags(merged)
    except Exception:
        return dict(fallback) if fallback is not None else dict(DEFAULT_SETTINGS)


def load_settings():
    """Cast display settings (the original settings profile)."""
    return _load_settings_file(SETTINGS_PATH)


def load_live_settings():
    """Browser/kiosk display settings, initially inherited from Cast.

    The live profile is only persisted after its editor is saved, so existing
    installations gain an identical-looking browser display without a
    migration step. Subsequent Cast edits cannot alter the live layout.
    """
    return _load_settings_file(LIVE_SETTINGS_PATH, fallback=load_settings())


def clean_block_position(position, template=None):
    """One block's safe layout/style fields; unknown keys are dropped."""
    item = {}
    limits = (("x", -10, 10), ("y", -8, 8), ("width", 12, 55),
              ("scale", .65, 1.5)) if template == "street" else (
              ("x", -100, 100), ("y", -100, 100),
              ("width", 5, 100), ("scale", 0.3, 3))
    for key, low, high in limits:
        number = position.get(key)
        if isinstance(number, (int, float)) and not isinstance(number, bool):
            item[key] = round(max(low, min(high, number)), 2)
    if position.get("align") in ("left", "center", "right"):
        item["align"] = position["align"]
    if position.get("font") in TITLE_FONTS:
        item["font"] = position["font"]
    if position.get("logoFit") in ("contain", "width", "natural"):
        item["logoFit"] = position["logoFit"]
    logo_zoom = position.get("logoZoom")
    if isinstance(logo_zoom, (int, float)) and not isinstance(logo_zoom, bool):
        item["logoZoom"] = round(max(50, min(200, logo_zoom)), 2)
    color = position.get("color")
    if isinstance(color, str) and ACCENT_RE.match(color):
        item["color"] = color
    for key in ("panelBackground", "panelBorder"):
        if isinstance(position.get(key), bool):
            item[key] = position[key]
    return item


def clean_custom_backdrop_settings(settings):
    """Clamp custom-art controls that are consumed directly by CSS."""
    settings["customBackdropEnabled"] = bool(settings.get("customBackdropEnabled"))
    if settings.get("customBackdropFit") not in ("cover", "contain", "fill"):
        settings["customBackdropFit"] = "cover"
    for key, low, high, default in (
            ("customBackdropZoom", 50, 300, 100),
            ("customBackdropX", 0, 100, 50),
            ("customBackdropY", 0, 100, 50),
            ("customBackdropOpacity", 5, 100, 35),
            ("customBackdropBlur", 0, 20, 0),
            ("customBackdropBrightness", 25, 150, 100)):
        settings[key] = clamp_setting(settings.get(key), low, high, default)
    return settings


def clean_block_layout(value):
    """{template: {block: position}}, limited to known templates/blocks."""
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for template, blocks in value.items():
        if template not in TEMPLATES or not isinstance(blocks, dict):
            continue
        per_template = {}
        for name, position in blocks.items():
            if name not in EDITABLE_BLOCKS or not isinstance(position, dict):
                continue
            item = clean_block_position(position, template)
            if item:
                per_template[name] = item
        if per_template:
            cleaned[template] = per_template
    return cleaned


def clean_block_visibility(value):
    """{template: {block: bool}} — sparse overrides of template defaults."""
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for template, blocks in value.items():
        if template not in TEMPLATES or not isinstance(blocks, dict):
            continue
        per_template = {name: bool(shown) for name, shown in blocks.items()
                        if name in TOGGLEABLE_BLOCKS and isinstance(shown, bool)}
        if per_template:
            cleaned[template] = per_template
    return cleaned


# Display-only keys a shared setup may carry along (never location or creds).
PRESET_EXTRA_KEYS = ("clockFormat", "clockSeconds", "weatherFX",
                     "streetRainAnimation", "showDeviceLocation",
                     "weatherIntensity", "weatherUnits",
                     "fanartType", "fanartRotateSeconds")


def clean_presets(value):
    """User-saved looks, capped and clamped: each rides the same cleaners as
    the live config so Import can't smuggle junk through a preset. `author`
    credits whoever exported a shared setup; `extras` are display-only keys."""
    if not isinstance(value, list):
        return []
    cleaned = []
    for preset in value[:20]:
        if not isinstance(preset, dict) or preset.get("template") not in TEMPLATES:
            continue
        name = preset.get("name")
        if not isinstance(name, str) or not name.strip():
            continue
        item = {
            "name": name.strip()[:40],
            "template": preset["template"],
            "blockLayout": clean_block_layout(preset.get("blockLayout")),
            "blockVisibility": clean_block_visibility(preset.get("blockVisibility")),
            "metaOpts": {k: bool(preset.get("metaOpts", {}).get(k, True))
                         for k in ("genres", "mediainfo", "rating", "runtime")},
        }
        author = preset.get("author")
        if isinstance(author, str) and author.strip():
            item["author"] = author.strip()[:40]
        extras = preset.get("extras")
        if isinstance(extras, dict):
            kept = {}
            for k in PRESET_EXTRA_KEYS:
                if k in extras:
                    kept[k] = extras[k]
            if kept.get("clockFormat") not in ("12h", "24h"):
                kept.pop("clockFormat", None)
            if kept.get("weatherUnits") not in ("f", "c"):
                kept.pop("weatherUnits", None)
            if not isinstance(kept.get("weatherIntensity"), int) \
                    or not 1 <= kept.get("weatherIntensity", 0) <= 4:
                kept.pop("weatherIntensity", None)
            for boolean in ("clockSeconds", "weatherFX",
                            "streetRainAnimation", "showDeviceLocation"):
                if boolean in kept and not isinstance(kept[boolean], bool):
                    kept.pop(boolean, None)
            if kept.get("fanartType") not in FANART_TYPES:
                kept.pop("fanartType", None)
            if not (isinstance(kept.get("fanartRotateSeconds"), int)
                    and 300 <= kept["fanartRotateSeconds"] <= 3600):
                kept.pop("fanartRotateSeconds", None)
            if kept:
                item["extras"] = kept
        cleaned.append(item)
    return cleaned


# Old flat presence gates -> per-template visibility overrides. The v2 settings
# page has no global show* switches; presence lives in blockVisibility (which
# now includes backdrop). Old saves and old exports still carry the flags, so
# fold them in wherever they say "off", then neutralize to True — idempotent,
# and an explicit visibility override always wins (setdefault).
# ponytail: one-shot migration like migrate_block_layout; delete both together.
SHOW_FLAG_BLOCKS = {"showPlot": "plot", "showClock": "clock",
                    "showScores": "ratings", "showProgress": "progress",
                    "showGenres": "category", "backdrop": "backdrop"}


def migrate_show_flags(settings):
    if not isinstance(settings.get("blockVisibility"), dict):
        settings["blockVisibility"] = {}
    for flag, block in SHOW_FLAG_BLOCKS.items():
        if settings.get(flag) is False:
            for template in TEMPLATES:
                if block in TEMPLATE_DEFAULT_BLOCKS[template]:
                    settings["blockVisibility"].setdefault(
                        template, {}).setdefault(block, False)
        settings[flag] = True
    return settings


def visible_blocks(template, visibility):
    """The block set actually shown for a template: its shipped default,
    with this template's blockVisibility overrides applied."""
    shown = set(TEMPLATE_DEFAULT_BLOCKS.get(template, ()))
    for name, on in (visibility or {}).get(template, {}).items():
        shown.add(name) if on else shown.discard(name)
    return shown


def clean_intensity(value):
    """Weather effect intensity: an int 1..4, default 2."""
    try:
        return min(4, max(1, int(value)))
    except (TypeError, ValueError):
        return 2


def serve_web():
    from marquee.api.http import handler_for
    from marquee.api.bridge import https_server
    import threading
    handler = handler_for(sys.modules[__name__])
    secure = https_server(handler, DATA_DIR)
    if secure:
        threading.Thread(target=secure.serve_forever, daemon=True).start()
    ThreadingHTTPServer(("", SERVE_PORT), handler).serve_forever()


# --- Log helpers -------------------------------------------------------------
# Color-coded, operator-actionable log lines. Unraid's Docker log viewer renders
# ANSI even though `docker logs` isn't a TTY; honor the NO_COLOR convention for
# anyone piping the logs elsewhere.
_NO_COLOR = bool(os.environ.get("NO_COLOR"))

def _color(code, s):
    return s if _NO_COLOR else f"\033[{code}m{s}\033[0m"

def log_ok(s):   print(_color("32", f"✓ {s}"), flush=True)   # green
def log_warn(s): print(_color("33", f"⚠ {s}"), flush=True)   # yellow
def log_err(s):  print(_color("31", f"✗ {s}"), flush=True)   # red

def current_host():
    """Configured host for the active backend, for diagnostic messages."""
    b = media_backend()
    host = plex_creds()[0] if b == "plex" else emby_creds(b)[0]
    return host or "(no host set)"

def explain_error(e):
    """Turn a raw poll-loop exception into one operator-actionable line, so
    'loop error: <urlopen error [Errno 111] Connection refused>' becomes
    'can't reach plex at http://…:32400 — connection refused (is it running?)'."""
    backend = media_backend()
    host = current_host()
    reason = getattr(e, "reason", e)              # URLError wraps the real cause
    errno = getattr(e, "errno", None) or getattr(reason, "errno", None)
    if isinstance(e, urllib.error.HTTPError):
        if e.code in (401, 403):
            return (f"{backend} rejected the credentials (HTTP {e.code}) — check "
                    f"the token / API key on the settings page")
        if e.code == 404:
            return f"{backend} path not found (HTTP 404) at {host} — wrong host?"
        return f"{backend} returned HTTP {e.code} from {host}"
    if isinstance(reason, socket.gaierror) or errno in (-2, -3, -5):
        return (f"can't resolve {host} — check the {backend.upper()}_HOST setting "
                f"(DNS lookup failed)")
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return f"{backend} at {host} timed out — server slow or unreachable"
    if isinstance(reason, ConnectionRefusedError) or errno == 111:
        return (f"can't reach {backend} at {host} — connection refused "
                f"(is the media server running?)")
    if isinstance(reason, ConnectionResetError) or errno == 104:
        return f"{backend} at {host} dropped the connection (reset) — retrying"
    return f"{backend} poll failed: {e}"


# Media services bind after configuration and logging are defined. Their
# exported callables become this composition module's service surface for the
# runtime and HTTP layers.
_media.bind(sys.modules[__name__])
globals().update(_media.exports())
