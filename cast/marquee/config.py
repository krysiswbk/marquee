"""Typed, durable configuration and migration for the Marquee fork."""
from __future__ import annotations

import json
import os
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from zoneinfo import ZoneInfo


DEFAULT_CONFIG = {
    "version": 5,
    "general": {
        "application_name": "Marquee", "timezone": "America/Toronto",
        "latitude": None, "longitude": None, "display_refresh_seconds": 0.5,
        "idle_behavior": "plex",
    },
    "display": {
        "rotation_seconds": 30, "transition_ms": 700,
        "minimum_context_seconds": 12, "default_screen": "plex",
        "live_rotation_seconds": 30, "live_fallback_every": 2,
        "secondary_screen_mode": "off",
        "kiosk_interaction_idle_seconds": 30,
    },
    "fallback": {
        "screen": "clock_weather", "rotate_relevant": True,
        "rotation_seconds": 20, "single_item_seconds": 12,
        "show_clock": True, "show_weather": True, "show_details": True,
        "show_artwork": True,
    },
    "context_engine": {
        "minimum_relevance": 35, "live_priority": 90,
        "starting_soon_minutes": 120, "post_event_minutes": 30,
        "post_event_plex_grace_minutes": 0, "takeovers_enabled": True,
    },
    "interests": {
        "sports_teams": ["TOR"], "sports": ["UFC", "PFL", "NHL"],
        "tracked_shows": [], "franchises": [], "artists": [],
        "gaming": [], "astronomy": True,
    },
    "providers": {
        "plex": {"enabled": True, "priority": 70},
        "nhl": {"enabled": True, "priority": 90, "teams": ["TOR"],
                "pregame_minutes": 120, "postgame_minutes": 180},
        "ufc": {"enabled": True, "priority": 90, "preevent_minutes": 120,
                "result_minutes": 30, "include_contender_series": True},
        "pfl": {"enabled": True, "priority": 90, "preevent_minutes": 120,
                "result_minutes": 30},
        "weather": {"enabled": True, "priority": 85, "radar": True,
                    "precip_probability": 55, "approach_minutes": 60,
                    "wind_gust_kmh": 70, "radar_span_degrees": 3.0,
                    "severe_takeover": True, "snow_enabled": True},
        "tv": {"enabled": False, "priority": 60, "url": "", "api_key": "",
               "tracked_shows": [], "lookahead_hours": 24,
               "tracking_mode": "show_all"},
        "astronomy": {"enabled": True, "priority": 50, "kp_threshold": 6.0,
                      "aurora": True, "iss": False, "meteor_showers": True,
                      "eclipses": True, "minimum_significance": 70},
        "movies": {"enabled": False, "priority": 55},
        "trailers": {"enabled": False, "priority": 50},
        "major_events": {"enabled": False, "priority": 40},
        "gaming": {"enabled": False, "priority": 45, "claims_url": "",
                   "lookback_days": 7, "claim_ttl_hours": 24,
                   "api_key": "", "email": "", "region": "ca",
                   "min_discount_percent": 50, "atl_min_discount_percent": 25,
                   "max_price_cad": 40, "max_deals": 3, "max_claims": 3,
                   "release_lookahead_days": 30, "max_releases": 3,
                   "release_priority": 45},
        "music": {"enabled": False, "priority": 60},
        "calendar": {"enabled": True, "priority": 40, "lookahead_days": 21,
                     "targets": ["kiosk"], "allow_cast": False,
                     "cast_min_priority": 95},
    },
}

SECRET_PATHS = {("providers", "tv", "api_key"), ("providers", "gaming", "api_key")}


def merge(base, update):
    result = deepcopy(base)
    for key, value in (update or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else:
            result[key] = value
    return result


def _number(value, low, high, name, integer=False):
    try:
        number = int(value) if integer else float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be a number")
    if not low <= number <= high:
        raise ValueError(f"{name} must be between {low} and {high}")
    return number


def _strings(value, name):
    if not isinstance(value, list):
        raise ValueError(f"{name} must be a list")
    return [str(item).strip()[:120] for item in value if str(item).strip()]


def validate_config(value):
    """Return a normalized complete config or raise a user-facing error."""
    if not isinstance(value, dict):
        raise ValueError("configuration must be an object")
    result = merge(DEFAULT_CONFIG, value)
    from .attention.schema import validate as validate_attention
    result["attention"] = validate_attention(result.get("attention", {}))
    result["version"] = 5
    general = result["general"]
    general["application_name"] = str(general["application_name"]).strip()[:60] or "Marquee"
    try:
        ZoneInfo(str(general["timezone"]))
    except Exception:
        raise ValueError("general.timezone must be a valid IANA timezone")
    for key, low, high in (("latitude", -90, 90), ("longitude", -180, 180)):
        if general[key] not in (None, ""):
            general[key] = _number(general[key], low, high, f"general.{key}")
        else:
            general[key] = None
    general["display_refresh_seconds"] = _number(
        general["display_refresh_seconds"], .25, 30, "general.display_refresh_seconds")
    if general["idle_behavior"] not in ("plex", "clock", "blank"):
        raise ValueError("general.idle_behavior is invalid")
    display = result["display"]
    display["rotation_seconds"] = _number(display["rotation_seconds"], 5, 3600,
                                           "display.rotation_seconds", True)
    display["live_rotation_seconds"] = _number(
        display["live_rotation_seconds"], 5, 3600,
        "display.live_rotation_seconds", True)
    display["live_fallback_every"] = _number(
        display["live_fallback_every"], 0, 20,
        "display.live_fallback_every", True)
    display["secondary_screen_mode"] = str(
        display.get("secondary_screen_mode", "off")).strip().lower()
    if display["secondary_screen_mode"] not in ("off", "weather", "mirror"):
        raise ValueError("display.secondary_screen_mode must be off, weather, or mirror")
    display["kiosk_interaction_idle_seconds"] = _number(
        display.get("kiosk_interaction_idle_seconds", 30), 5, 600,
        "display.kiosk_interaction_idle_seconds", True)
    display["transition_ms"] = _number(display["transition_ms"], 0, 5000,
                                        "display.transition_ms", True)
    display["minimum_context_seconds"] = _number(
        display["minimum_context_seconds"], 0, 600, "display.minimum_context_seconds", True)
    if display["minimum_context_seconds"] > display["rotation_seconds"]:
        raise ValueError("display.minimum_context_seconds cannot exceed display.rotation_seconds")
    fallback = result["fallback"]
    if fallback["screen"] not in ("clock_weather", "ambient", "plex", "blank"):
        raise ValueError("fallback.screen is invalid")
    fallback["rotation_seconds"] = _number(
        fallback["rotation_seconds"], 5, 3600, "fallback.rotation_seconds", True)
    fallback["single_item_seconds"] = _number(
        fallback["single_item_seconds"], 5, 600, "fallback.single_item_seconds", True)
    if fallback["single_item_seconds"] > fallback["rotation_seconds"]:
        raise ValueError("fallback.single_item_seconds cannot exceed fallback.rotation_seconds")
    for key in ("rotate_relevant", "show_clock", "show_weather", "show_details",
                "show_artwork"):
        fallback[key] = bool(fallback[key])
    engine = result["context_engine"]
    for key, low, high in (("minimum_relevance", 0, 100), ("live_priority", 0, 100),
                           ("starting_soon_minutes", 1, 1440),
                           ("post_event_minutes", 0, 1440),
                           ("post_event_plex_grace_minutes", 0, 120)):
        engine[key] = _number(engine[key], low, high, f"context_engine.{key}", True)
    engine["takeovers_enabled"] = bool(engine["takeovers_enabled"])
    interests = result["interests"]
    for key in ("sports_teams", "sports", "tracked_shows", "franchises",
                "artists", "gaming"):
        interests[key] = _strings(interests.get(key, []), f"interests.{key}")
    for name, provider in result["providers"].items():
        if not isinstance(provider, dict):
            raise ValueError(f"providers.{name} must be an object")
        provider["enabled"] = bool(provider.get("enabled"))
        provider["priority"] = _number(provider.get("priority", 40), 0, 100,
                                       f"providers.{name}.priority", True)
        if name in ("movies", "trailers", "major_events", "music"):
            # These are diagnostic placeholders, not installable adapters.
            # Persisting an enabled checkbox would falsely imply a setup path.
            provider["enabled"] = False
    weather = result["providers"]["weather"]
    weather["precip_probability"] = _number(weather["precip_probability"], 0, 100,
                                            "providers.weather.precip_probability", True)
    weather["approach_minutes"] = _number(weather["approach_minutes"], 5, 360,
                                          "providers.weather.approach_minutes", True)
    weather["radar_span_degrees"] = _number(weather["radar_span_degrees"], .2, 12,
                                             "providers.weather.radar_span_degrees")
    weather["wind_gust_kmh"] = _number(weather["wind_gust_kmh"], 20, 250,
                                       "providers.weather.wind_gust_kmh")
    nhl = result["providers"]["nhl"]
    nhl["pregame_minutes"] = _number(nhl.get("pregame_minutes", 120), 0, 1440,
                                      "providers.nhl.pregame_minutes", True)
    nhl["teams"] = _strings(nhl.get("teams", []), "providers.nhl.teams")
    for league in ("ufc", "pfl"):
        mma = result["providers"][league]
        mma["preevent_minutes"] = _number(mma.get("preevent_minutes", 120), 0, 1440,
                                            f"providers.{league}.preevent_minutes", True)
        mma["result_minutes"] = _number(mma.get("result_minutes", 30), 0, 1440,
                                          f"providers.{league}.result_minutes", True)
    ufc = result["providers"]["ufc"]
    ufc["include_contender_series"] = bool(ufc.get("include_contender_series", True))
    astronomy = result["providers"]["astronomy"]
    astronomy["kp_threshold"] = _number(astronomy["kp_threshold"], 0, 9,
                                        "providers.astronomy.kp_threshold")
    astronomy["minimum_significance"] = _number(
        astronomy.get("minimum_significance", 70), 0, 100,
        "providers.astronomy.minimum_significance", True)
    tv = result["providers"]["tv"]
    tv["url"] = str(tv.get("url", "")).strip().rstrip("/")[:500]
    tv["api_key"] = str(tv.get("api_key", "")).strip()[:500]
    tv["tracked_shows"] = _strings(tv.get("tracked_shows", []),
                                   "providers.tv.tracked_shows")
    tv["tracking_mode"] = str(tv.get("tracking_mode", "show_all")).strip().lower()
    if tv["tracking_mode"] not in ("show_all", "tracked_only"):
        raise ValueError("providers.tv.tracking_mode must be show_all or tracked_only")
    tv["lookahead_hours"] = _number(tv.get("lookahead_hours", 24), 1, 168,
                                     "providers.tv.lookahead_hours", True)
    gaming = result["providers"]["gaming"]
    gaming["claims_url"] = str(gaming.get("claims_url", "")).strip()[:500]
    gaming["lookback_days"] = _number(gaming.get("lookback_days", 7), 1, 30,
                                      "providers.gaming.lookback_days", True)
    gaming["claim_ttl_hours"] = _number(gaming.get("claim_ttl_hours", 24), 1, 48,
                                         "providers.gaming.claim_ttl_hours", True)
    gaming["api_key"] = str(gaming.get("api_key", "")).strip()[:500]
    gaming["email"] = str(gaming.get("email", "")).strip()[:320]
    gaming["region"] = str(gaming.get("region", "ca")).strip().lower()[:8] or "ca"
    gaming["min_discount_percent"] = _number(gaming.get("min_discount_percent", 50), 1, 100,
                                               "providers.gaming.min_discount_percent", True)
    gaming["atl_min_discount_percent"] = _number(gaming.get("atl_min_discount_percent", 25), 1, 100,
                                                   "providers.gaming.atl_min_discount_percent", True)
    gaming["max_price_cad"] = _number(gaming.get("max_price_cad", 40), 0, 500,
                                       "providers.gaming.max_price_cad")
    gaming["max_deals"] = _number(gaming.get("max_deals", 3), 1, 10,
                                   "providers.gaming.max_deals", True)
    gaming["max_claims"] = _number(gaming.get("max_claims", 3), 1, 10,
                                    "providers.gaming.max_claims", True)
    gaming["release_lookahead_days"] = _number(
        gaming.get("release_lookahead_days", 30), 1, 180,
        "providers.gaming.release_lookahead_days", True)
    gaming["max_releases"] = _number(gaming.get("max_releases", 3), 1, 10,
                                      "providers.gaming.max_releases", True)
    gaming["release_priority"] = _number(gaming.get("release_priority", gaming["priority"]),
                                          0, 100, "providers.gaming.release_priority", True)
    calendar = result["providers"]["calendar"]
    calendar["lookahead_days"] = _number(calendar.get("lookahead_days", 21), 1, 90,
                                           "providers.calendar.lookahead_days", True)
    targets = calendar.get("targets", ["kiosk"])
    if not isinstance(targets, list) or not targets or any(x not in ("kiosk", "hubs") for x in targets):
        raise ValueError("providers.calendar.targets must contain kiosk and/or hubs")
    calendar["allow_cast"] = bool(calendar.get("allow_cast", False))
    calendar["cast_min_priority"] = _number(calendar.get("cast_min_priority", 95), 80, 100,
                                              "providers.calendar.cast_min_priority", True)
    return result


def _atomic_json(path, value, mode=0o600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".config-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


@dataclass
class ConfigRepository:
    data_dir: str
    env: dict | None = None

    @property
    def path(self):
        return os.path.join(self.data_dir, "marquee.json")

    @property
    def legacy_provider_path(self):
        return os.path.join(self.data_dir, "providers.json")

    def _read(self, path):
        try:
            with open(path) as handle:
                value = json.load(handle)
            return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def migrate(self):
        if os.path.exists(self.path):
            return False
        old = self._read(self.legacy_provider_path)
        display_settings = self._read(os.path.join(self.data_dir, "settings.json"))
        migrated = {}
        if old:
            migrated = {
                "general": old.get("location", {}),
                "interests": old.get("interests", {}),
                "providers": old.get("providers", {}),
            }
            location = migrated["general"]
            if "timezone" not in location:
                location["timezone"] = "America/Toronto"
        if display_settings.get("rotateSeconds") is not None:
            migrated.setdefault("display", {})["rotation_seconds"] = display_settings["rotateSeconds"]
        _atomic_json(self.path, validate_config(migrated))
        return True

    def stored(self):
        self.migrate()
        value = self._read(self.path)
        # v2 shipped with a three-hour UFC result default. Migrate installations
        # that still carry that untouched default to the household-friendly
        # thirty-minute recap; explicit non-default choices are preserved.
        version = int(value.get("version", 1))
        if version < 3:
            ufc = (value.get("providers") or {}).get("ufc") or {}
            if ufc.get("result_minutes", 180) == 180:
                ufc["result_minutes"] = 30
            engine = value.setdefault("context_engine", {})
            if engine.get("post_event_minutes", 180) == 180:
                engine["post_event_minutes"] = 30
        if version < 4:
            engine = value.setdefault("context_engine", {})
            if engine.get("post_event_plex_grace_minutes", 5) == 5:
                engine["post_event_plex_grace_minutes"] = 0
        if version < 5:
            value.setdefault("fallback", deepcopy(DEFAULT_CONFIG["fallback"]))
            value["version"] = 5
            value = validate_config(value)
            _atomic_json(self.path, value)
        return validate_config(value)

    def effective(self):
        config = self.stored()
        env = self.env if self.env is not None else os.environ
        general, tv = config["general"], config["providers"]["tv"]
        if env.get("MARQUEE_LATITUDE"):
            general["latitude"] = float(env["MARQUEE_LATITUDE"])
        if env.get("MARQUEE_LONGITUDE"):
            general["longitude"] = float(env["MARQUEE_LONGITUDE"])
        if env.get("MARQUEE_TIMEZONE"):
            general["timezone"] = env["MARQUEE_TIMEZONE"]
        if env.get("SONARR_URL"):
            tv.update(enabled=True, url=env["SONARR_URL"].rstrip("/"))
        if env.get("SONARR_API_KEY"):
            tv["api_key"] = env["SONARR_API_KEY"]
        return validate_config(config)

    def save(self, incoming):
        incoming = deepcopy(incoming)
        for section, provider, field in SECRET_PATHS:
            (incoming.get(section, {}).get(provider, {})).pop(field + "_set", None)
        current = self.stored()
        merged = merge(current, incoming)
        # Empty write-only secret fields retain the durable value.
        for path in SECRET_PATHS:
            section, provider, field = path
            typed = (((incoming.get(section) or {}).get(provider) or {}).get(field))
            if typed in (None, ""):
                merged[section][provider][field] = current[section][provider][field]
        validated = validate_config(merged)
        _atomic_json(self.path, validated)
        return validated

    def public(self):
        value = self.stored()
        for section, provider, field in SECRET_PATHS:
            secret = value[section][provider].pop(field, "")
            value[section][provider][field + "_set"] = bool(secret)
        return value
