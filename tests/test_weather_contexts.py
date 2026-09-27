from datetime import datetime, timezone
import unittest

from cast.marquee.providers.weather import WeatherProvider


NOW = datetime(2026, 9, 9, 16, tzinfo=timezone.utc)


class WeatherContextTests(unittest.TestCase):
    def test_radar_requests_transparent_wms_frames(self):
        provider = WeatherProvider({"enabled": True, "timezone": "UTC",
                                    "latitude": 43.7, "longitude": -79.4}, "/tmp")
        _, url = provider._radar_url()
        self.assertIn("TRANSPARENT=TRUE", url)

    def test_current_conditions_supply_low_priority_kiosk_context(self):
        provider = WeatherProvider({"enabled": True, "timezone": "UTC",
                                    "latitude": 43.7, "longitude": -79.4}, "/tmp")
        payload = {"forecast": {"current": {"temperature_2m": 21.4,
                                             "wind_gusts_10m": 18},
                                "hourly": {"time": []}},
                   "alerts": {"features": []},
                   "snapshot": {"summary": "Clear this afternoon"}}
        current = next(c for c in provider.contexts(payload, NOW)
                       if c.id == "weather:current")
        self.assertEqual(current.body, "Clear this afternoon")
        self.assertNotIn(current.body, current.stats)
        self.assertEqual(current.priority, 30)
        self.assertEqual(current.targets, ["kiosk"])
        self.assertEqual(current.title, "Weather at home")
        self.assertGreater(current.expires_at, NOW)


class BroadcastWeatherTests(unittest.TestCase):
    def provider(self):
        return WeatherProvider({"enabled": True, "timezone": "America/Toronto",
                                "latitude": 43.7, "longitude": -79.4}, "/tmp")

    def payload(self, precipitation=0):
        return {"forecast": {"current": {"temperature_2m": 24, "weather_code": 0,
                                        "precipitation": precipitation, "is_day": 1},
            "hourly": {"time": [f"2026-09-09T{h}:00" for h in range(12, 22)],
                       "temperature_2m": [24, 23, 22, 21, 20, 19, 18, 17, 16, 15],
                       "weather_code": [0]*10, "precipitation_probability": [0]*10},
            "daily": {"time": [f"2026-09-{d:02}" for d in range(9, 16)],
                      "temperature_2m_max": [25]*7, "temperature_2m_min": [14]*7,
                      "weather_code": [0]*7}}, "alerts": {"features": []}}

    def test_clear_conditions_have_six_hours_five_days_and_no_radar(self):
        value = self.provider().contexts(self.payload(), NOW)[0].display_dict()["weather"]
        self.assertFalse(value["radar_relevant"])
        self.assertEqual(len(value["hours"]), 6)
        self.assertEqual(len(value["days"]), 5)
        self.assertTrue(value["hours"][0]["at"].endswith("-04:00"))
        self.assertEqual(value["days"][0]["high"], 25)
        self.assertIsNone(value["days"][0]["rain"])

    def test_active_and_approaching_precipitation_request_radar(self):
        contexts = self.provider().contexts(self.payload(.5), NOW)
        self.assertTrue(all(c.raw["weather"]["radar_relevant"] for c in contexts))
        payload = self.payload()
        payload["forecast"]["hourly"]["precipitation_probability"][2] = 85
        payload["forecast"]["hourly"]["precipitation"] = [0, 0, .4]
        self.assertTrue(self.provider().contexts(payload, NOW)[0].raw["weather"]["radar_relevant"])

    def test_partial_forecasts_keep_missing_temperatures_unknown(self):
        payload = self.payload()
        del payload["forecast"]["hourly"]["temperature_2m"]
        del payload["forecast"]["daily"]["temperature_2m_max"]
        value = self.provider().contexts(payload, NOW)[0].raw["weather"]
        self.assertIsNone(value["hours"][0]["temp"])
        self.assertIsNone(value["days"][0]["high"])


class BroadcastMetadataTests(unittest.TestCase):
    provider = BroadcastWeatherTests.provider
    payload = BroadcastWeatherTests.payload
    def test_observation_and_sun_times_carry_source_timezone(self):
        payload = self.payload()
        payload["forecast"]["current"]["time"] = "2026-09-09T12:00"
        payload["forecast"]["daily"]["sunset"] = ["2026-09-09T19:40"]
        value = self.provider().weather_brief(payload, NOW)
        self.assertEqual(value["observed_at"], "2026-09-09T12:00:00-04:00")
        self.assertEqual(value["days"][0]["sunset"], "2026-09-09T19:40:00-04:00")
        self.assertIsNone(value["days"][0]["sunrise"])

    def test_quiet_weather_exposes_original_radar_and_its_real_timestamp(self):
        import os
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as directory:
            provider = self.provider()
            provider.data_dir = directory
            radar = Path(directory) / "provider-assets" / "weather-radar.img"
            radar.parent.mkdir()
            radar.write_bytes(b"test fixture")
            os.utime(radar, (NOW.timestamp(), NOW.timestamp()))
            value = provider.contexts(self.payload(), NOW)[0].raw["weather"]
            self.assertEqual(value["radar_updated_at"], NOW.timestamp())
            self.assertTrue(value["radar_url"].startswith("/provider-assets/weather-radar.img?v="))
            self.assertFalse(value["radar_relevant"])
