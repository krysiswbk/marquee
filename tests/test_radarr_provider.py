from datetime import datetime, timedelta, timezone

import pytest

from marquee.config import ConfigRepository, DEFAULT_CONFIG
from marquee.providers.radarr import RadarrProvider
from marquee.providers.registry import create_providers


NOW = datetime(2026, 10, 7, 12, tzinfo=timezone.utc)


class Client:
    def __init__(self):
        self.request = None

    def json(self, url, headers=None):
        self.request = (url, headers)
        return []


def test_radarr_fetch_uses_calendar_window_and_api_key(tmp_path):
    client = Client()
    provider = RadarrProvider({"enabled": True, "url": "http://radarr:7878/",
                               "api_key": "secret", "lookahead_days": 30},
                              tmp_path, client=client)
    provider.config["_now"] = NOW
    assert provider.fetch() == []
    assert client.request[0].startswith("http://radarr:7878/api/v3/calendar?")
    assert "end=2026-11-06" in client.request[0]
    assert client.request[1] == {"X-Api-Key": "secret"}


def test_radarr_builds_upcoming_movie_context_and_filters_invalid_items(tmp_path):
    provider = RadarrProvider({"enabled": True, "priority": 55, "lookahead_days": 90}, tmp_path)
    release = NOW + timedelta(days=2)
    payload = [
        {"id": 12, "title": "Example Film", "year": 2027,
         "digitalRelease": release.isoformat(), "tmdbId": 123,
         "images": [{"coverType": "poster", "remoteUrl": "https://art/poster.jpg"}]},
        {"id": 13, "title": "TBA", "digitalRelease": release.isoformat()},
        {"id": 14, "title": "Already Available", "hasFile": True,
         "digitalRelease": release.isoformat()},
        {"id": 15, "title": "No date"},
    ]
    contexts = provider.contexts(payload, NOW)
    assert len(contexts) == 1
    card = contexts[0].display_dict()
    assert card["id"] == "radarr:12"
    assert card["type"] == "movie_release"
    assert card["title"] == "Example Film"
    assert card["artwork"] == "https://art/poster.jpg"
    assert card["sourceUrl"] == "https://www.themoviedb.org/movie/123"
    assert card["targets"] == ["kiosk"]


def test_movies_provider_is_registered_and_secret_is_write_only(tmp_path):
    config = {**DEFAULT_CONFIG, "general": {**DEFAULT_CONFIG["general"],
                                             "latitude": 43.5, "longitude": -79.9}}
    config["providers"] = {**DEFAULT_CONFIG["providers"],
                           "movies": {"enabled": True, "priority": 55,
                                      "url": "http://radarr:7878", "api_key": "secret",
                                      "lookahead_days": 90}}
    providers = {provider.name: provider for provider in create_providers(config, tmp_path)}
    assert isinstance(providers["movies"], RadarrProvider)
    assert providers["movies"].enabled

    repository = ConfigRepository(tmp_path, env={})
    repository.save({"providers": {"movies": {"enabled": True,
                                                "url": "http://radarr:7878",
                                                "api_key": "secret"}}})
    assert repository.public()["providers"]["movies"]["api_key_set"]
    assert "api_key" not in repository.public()["providers"]["movies"]


def test_radarr_environment_config_enables_movies_and_supplies_credentials(tmp_path):
    repo = ConfigRepository(tmp_path, env={"RADARR_URL": "http://radarr:7878/",
                                           "RADARR_API_KEY": "environment-secret"})
    movies = repo.effective()["providers"]["movies"]
    assert movies["enabled"]
    assert movies["url"] == "http://radarr:7878"
    assert movies["api_key"] == "environment-secret"


def test_radarr_requires_url_and_key(tmp_path):
    provider = RadarrProvider({"enabled": True}, tmp_path)
    with pytest.raises(ValueError, match="RADARR_URL / RADARR_API_KEY"):
        provider.fetch()
