import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

from cast.marquee.providers.engine import ContextEngine, provider_error_summary
from cast.marquee.providers.model import Context, EventState
from cast.marquee.providers.sonarr import SonarrProvider
from cast.marquee.providers.weather import WeatherProvider
from unittest.mock import Mock


NOW = datetime(2026, 9, 8, 22, 0, tzinfo=timezone.utc)


class Client:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = 0
    def json(self, *args, **kwargs):
        self.calls += 1
        if self.error: raise self.error
        return self.responses.pop(0)
    def bytes(self, *args, **kwargs):
        return b"\x89PNG\r\n\x1a\nmock", "image/png"


def forecast(prob=0, amount=0, current=0):
    return {"current": {"temperature_2m": 20, "precipitation": current,
                        "rain": current, "snowfall": 0, "wind_gusts_10m": 10},
            "hourly": {"time": ["2026-09-08T18:30", "2026-09-08T19:00"],
                       "precipitation_probability": [prob, prob],
                       "precipitation": [amount, amount], "rain": [amount, amount],
                       "snowfall": [0, 0], "weather_code": [3, 61],
                       "wind_gusts_10m": [10, 10]}}


class ModelTests(unittest.TestCase):
    def test_provider_failure_summary_hides_implementation_details(self):
        raw = "Command '['curl', '-sS', 'https://nhl.example.test/feed'] returned non-zero exit status 22."
        summary = provider_error_summary(RuntimeError(raw))
        self.assertEqual(summary, "The provider request failed. Check the source connection or try again.")
        self.assertNotIn("curl", summary)
        self.assertNotIn("returned non-zero exit status", summary)

    def test_context_expiration(self):
        c = Context("x", "test", "test", "X", expires_at=NOW-timedelta(seconds=1))
        self.assertTrue(c.expired(NOW))

    def test_priority_and_factors(self):
        high = Context("h", "a", "x", "H", priority=80)
        low = Context("l", "b", "x", "L", priority=60, relevance=100)
        self.assertGreater(high.score(), low.score())

    def test_competing_candidates(self):
        a = Context("a", "one", "x", "A", priority=60, expires_at=NOW+timedelta(hours=1))
        b = Context("b", "two", "x", "B", priority=90, expires_at=NOW+timedelta(hours=1))
        engine = ContextEngine([], clock=lambda: NOW.timestamp())
        engine.candidates = {"mock": [a, b]}
        self.assertEqual(engine.winner().id, "b")

    def test_lifecycle_values(self):
        self.assertEqual([x.value for x in EventState][0:4],
                         ["UPCOMING", "STARTING_SOON", "LIVE", "RESULT"])

    def test_result_context_naturally_expires(self):
        result = Context("r", "sports", "result", "Winner", event_state=EventState.RESULT,
                         priority=95, expires_at=NOW + timedelta(seconds=12))
        self.assertFalse(result.expired(NOW))
        self.assertTrue(result.expired(NOW + timedelta(seconds=13)))


class ProviderTests(unittest.TestCase):
    def setUp(self): self.tmp = tempfile.TemporaryDirectory()
    def tearDown(self): self.tmp.cleanup()

    def weather(self, prob=0, amount=0, current=0, alerts=None):
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9,
             "timezone": "America/Toronto", "radar": False, "precip_probability": 55},
             self.tmp.name, Client([forecast(prob, amount, current),
                                    {"features": alerts or []}]))
        return p, p.contexts({"forecast": forecast(prob, amount, current), "alerts": {"features": alerts or []}}, NOW)

    def test_provider_disabled(self):
        p = WeatherProvider({"enabled": False}, self.tmp.name, Client())
        engine = ContextEngine([p], clock=lambda: NOW.timestamp()); engine.tick()
        self.assertEqual(engine.health["weather"]["state"], "disabled")

    def test_provider_diagnostics_are_safe_but_event_keeps_raw_evidence(self):
        raw = "Command '['curl', '-sS', 'https://nhl.example.test/feed'] returned non-zero exit status 22."
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9},
                            self.tmp.name, Client(error=RuntimeError(raw)))
        p.fetch = Mock(side_effect=RuntimeError(raw))
        events = Mock()
        engine = ContextEngine([p], clock=lambda: NOW.timestamp(), event_bus=events)
        engine.tick()
        with self.assertRaises(RuntimeError):
            engine.futures["weather"].result()
        engine.tick()
        health = engine.diagnostics()["providers"]["weather"]
        self.assertEqual(health["state"], "error")
        self.assertNotIn("curl", str(health))
        self.assertNotIn("returned non-zero exit status", str(health))
        event = next(call for call in events.publish.call_args_list
                      if call.args[0] == "provider.error")
        self.assertIn("curl", event.kwargs["error"])

    def test_timeout_without_cache(self):
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9}, self.tmp.name,
                            Client(error=TimeoutError("timed out")))
        p.fetch = Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError): p.cached_fetch()

    def test_rate_limit_without_cache(self):
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9}, self.tmp.name,
                            Client(error=RuntimeError("HTTP 429")))
        p.fetch = Mock(side_effect=RuntimeError("HTTP 429"))
        with self.assertRaisesRegex(RuntimeError, "429"): p.cached_fetch()

    def test_cached_response_on_error(self):
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9}, self.tmp.name, Client(error=TimeoutError()))
        os.makedirs(os.path.dirname(p.cache_path), exist_ok=True)
        with open(p.cache_path, "w") as handle:
            json.dump({"at": time.time(), "payload": {"cached": True}}, handle)
        payload, stale = p.cached_fetch()
        self.assertTrue(stale); self.assertTrue(payload["cached"])

    def test_stale_cache_rejected(self):
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9}, self.tmp.name, Client(error=TimeoutError()))
        os.makedirs(os.path.dirname(p.cache_path), exist_ok=True)
        with open(p.cache_path, "w") as handle:
            json.dump({"at": 1, "payload": {}}, handle)
        p.fetch = Mock(side_effect=TimeoutError())
        with self.assertRaises(TimeoutError): p.cached_fetch()

    def test_malformed_response(self):
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9,
                             "timezone": "America/Toronto", "radar": False},
                            self.tmp.name, Client([{"bad": True}, {"features": []}]))
        self.assertEqual(p.contexts({"forecast": {"bad": True}}, NOW), [])

    def test_rain_approaching_threshold(self):
        _, contexts = self.weather(prob=80, amount=.4)
        self.assertEqual(contexts[0].event_state, EventState.STARTING_SOON)
        self.assertEqual(contexts[0].subtype, "rain")

    def test_active_rain_live(self):
        _, contexts = self.weather(current=.2)
        self.assertEqual(contexts[0].event_state, EventState.LIVE)

    def test_weather_alert(self):
        alert = {"id": "a", "properties": {"event": "Thunderstorm warning",
                 "severity": "Severe", "expires": "2026-09-09T01:00:00Z"}}
        _, contexts = self.weather(alerts=[alert])
        self.assertEqual(contexts[0].priority, 92)

    def test_weather_alert_count_only_snapshot_value_is_ignored(self):
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9,
                             "timezone": "America/Toronto", "radar": False}, self.tmp.name)
        with open(os.path.join(self.tmp.name, "ha-weather.json"), "w") as handle:
            json.dump({"entity_id": "weather.home", "temp": 20, "condition": "sunny",
                       "code": 0, "isDay": True, "humidity": 50, "wind": 5,
                       "wind_gust": 10, "updated": time.time()}, handle)
        with open(os.path.join(self.tmp.name, "ha-weather-context.json"), "w") as handle:
            json.dump({"updated": time.time(), "advisories": 1}, handle)
        self.assertEqual(p.fetch()["alerts"]["features"], [])

    def test_weather_alert_real_snapshot_text_is_preserved(self):
        p = WeatherProvider({"enabled": True, "latitude": 43.5, "longitude": -79.9,
                             "timezone": "America/Toronto", "radar": False}, self.tmp.name)
        with open(os.path.join(self.tmp.name, "ha-weather.json"), "w") as handle:
            json.dump({"entity_id": "weather.home", "temp": 20, "condition": "sunny",
                       "code": 0, "isDay": True, "humidity": 50, "wind": 5,
                       "wind_gust": 10, "updated": time.time()}, handle)
        with open(os.path.join(self.tmp.name, "ha-weather-context.json"), "w") as handle:
            json.dump({"updated": time.time(), "advisories": "Heat warning in effect"}, handle)
        self.assertEqual(
            p.fetch()["alerts"]["features"][0]["properties"]["event"],
            "Heat warning in effect",
        )

    def sonarr(self, tracked=None):
        config = {"enabled": True, "url": "http://sonarr", "api_key": "x",
                  "timezone": "America/Toronto", "tracked_shows": tracked or [], "_now": NOW}
        episode = {"id": 1, "airDateUtc": "2026-09-08T23:00:00Z", "seasonNumber": 2,
                   "episodeNumber": 1, "title": "Return", "hasFile": False,
                   "series": {"title": "Severance", "monitored": True, "images": []}}
        p = SonarrProvider(config, self.tmp.name, Client([[episode]]))
        return p, episode

    def test_tracked_media_accepted_and_starting_soon(self):
        p, _ = self.sonarr(["Severance"])
        contexts = p.contexts(p.fetch(), NOW)
        self.assertEqual(contexts[0].event_state, EventState.STARTING_SOON)
        self.assertEqual(contexts[0].subtype, "season_premiere")

    def test_irrelevant_media_filtered(self):
        p, _ = self.sonarr(["The Bear"])
        self.assertEqual(p.contexts(p.fetch(), NOW), [])

    def test_timezone_boundary(self):
        p, episode = self.sonarr(["Severance"])
        episode["airDateUtc"] = "2026-09-09T02:30:00Z"  # still Sep 8 Toronto
        c = p.contexts([episode], NOW)[0]
        self.assertEqual(c.body, "Airs tonight")

    def test_live_and_post_transitions(self):
        p, episode = self.sonarr(["Severance"])
        episode["airDateUtc"] = "2026-09-08T21:50:00Z"
        self.assertEqual(p.contexts([episode], NOW)[0].event_state, EventState.LIVE)
        episode["hasFile"] = True
        self.assertEqual(p.contexts([episode], NOW), [])


if __name__ == "__main__": unittest.main()
