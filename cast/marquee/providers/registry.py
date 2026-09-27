from .astronomy import AstronomyProvider
from .sonarr import SonarrProvider
from .weather import WeatherProvider
from .sports import NHLProvider, UFCProvider, PFLProvider
from .gaming import GamingProvider
from .calendar import CalendarProvider
from .provider import Provider
from marquee.config import ConfigRepository, DEFAULT_CONFIG, merge


class OptionalProvider(Provider):
    """Visible diagnostic slot for adapters that require an explicit source choice."""
    def fetch(self):
        raise ValueError(self.config.get("requires", "provider adapter not configured"))
    def contexts(self, payload, now):
        return []


def load_provider_config(data_dir, env=None):
    return ConfigRepository(data_dir, env).effective()


def create_providers(config, data_dir, client=None):
    location = config.get("general") or config.get("location", {})
    providers = []
    mapping = (("nhl", NHLProvider), ("ufc", UFCProvider), ("pfl", PFLProvider),
               ("weather", WeatherProvider), ("tv", SonarrProvider),
               ("astronomy", AstronomyProvider), ("gaming", GamingProvider),
               ("calendar", CalendarProvider))
    for name, cls in mapping:
        item = {**config["providers"][name], **location}
        item["_minimum_relevance"] = config["context_engine"]["minimum_relevance"]
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
        "music": "configure Music Assistant, ListenBrainz, or Last.fm adapter",
    }
    for name, requires in requirements.items():
        cls = type(name.title().replace("_", "") + "Provider", (OptionalProvider,), {"name": name})
        item = {**config["providers"][name], "enabled": False, "requires": requires,
                "disabled_reason": "integration unavailable: " + requires}
        providers.append(cls(item, data_dir, client=client))
    return providers
