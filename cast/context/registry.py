import json
import os
from copy import deepcopy

from .astronomy import AstronomyProvider
from .sonarr import SonarrProvider
from .weather import WeatherProvider
from .provider import Provider


class OptionalProvider(Provider):
    """Visible diagnostic slot for adapters that require an explicit source choice."""
    def fetch(self):
        raise ValueError(self.config.get("requires", "provider adapter not configured"))
    def contexts(self, payload, now):
        return []


DEFAULT_CONFIG = {
    "version": 1,
    "location": {"latitude": None, "longitude": None, "timezone": "America/Toronto"},
    "interests": {"sports_teams": ["TOR"], "sports": ["UFC", "NHL"],
                  "tracked_shows": [], "franchises": [], "artists": [],
                  "gaming": [], "astronomy": True},
    "providers": {
        "weather": {"enabled": True, "radar": True, "precip_probability": 55,
                    "wind_gust_kmh": 70, "radar_span_degrees": 3.0},
        "tv": {"enabled": False, "url": "", "api_key": "", "tracked_shows": []},
        "astronomy": {"enabled": True, "kp_threshold": 6.0},
        "movies": {"enabled": False}, "trailers": {"enabled": False},
        "major_events": {"enabled": False}, "gaming": {"enabled": False},
        "music": {"enabled": False},
    },
}


def merge(base, update):
    result = deepcopy(base)
    for key, value in (update or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = merge(result[key], value)
        else: result[key] = value
    return result


def load_provider_config(data_dir, env=None):
    env = env or os.environ
    path = os.path.join(data_dir, "providers.json")
    try:
        with open(path) as handle: saved = json.load(handle)
    except (OSError, ValueError):
        saved = {}
    config = merge(DEFAULT_CONFIG, saved)
    location = config["location"]
    if env.get("MARQUEE_LATITUDE"): location["latitude"] = float(env["MARQUEE_LATITUDE"])
    if env.get("MARQUEE_LONGITUDE"): location["longitude"] = float(env["MARQUEE_LONGITUDE"])
    if env.get("MARQUEE_TIMEZONE"): location["timezone"] = env["MARQUEE_TIMEZONE"]
    tv = config["providers"]["tv"]
    if env.get("SONARR_URL"): tv.update(enabled=True, url=env["SONARR_URL"])
    if env.get("SONARR_API_KEY"): tv.update(api_key=env["SONARR_API_KEY"])
    return config


def create_providers(config, data_dir, client=None):
    location = config["location"]
    providers = []
    mapping = (("weather", WeatherProvider), ("tv", SonarrProvider),
               ("astronomy", AstronomyProvider))
    for name, cls in mapping:
        item = {**config["providers"][name], **location}
        if name == "tv":
            item["tracked_shows"] = item.get("tracked_shows") or config["interests"].get("tracked_shows", [])
        if name == "weather" and (location.get("latitude") is None or location.get("longitude") is None):
            item["enabled"] = False
            item["disabled_reason"] = "location not configured"
        providers.append(cls(item, data_dir, client=client))
    requirements = {
        "movies": "configure TMDb and/or Radarr relevance source",
        "trailers": "configure TMDb API key or approved official-channel feeds",
        "major_events": "enable and configure explicit event interests",
        "gaming": "configure selected platform/showcase feeds",
        "music": "configure Music Assistant, ListenBrainz, or Last.fm adapter",
    }
    for name, requires in requirements.items():
        cls = type(name.title().replace("_", "") + "Provider", (OptionalProvider,), {"name": name})
        item = {**config["providers"][name], "requires": requires}
        providers.append(cls(item, data_dir, client=client))
    return providers
