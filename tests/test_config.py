import json
import os
import tempfile
import unittest

from cast.marquee.config import ConfigRepository, validate_config


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
    def tearDown(self):
        self.tmp.cleanup()

    def test_migrates_legacy_provider_configuration_once(self):
        with open(os.path.join(self.tmp.name, "providers.json"), "w") as handle:
            json.dump({"location": {"latitude": 43.5, "longitude": -79.9},
                       "providers": {"weather": {"precip_probability": 63}},
                       "interests": {"sports_teams": ["TOR"]}}, handle)
        with open(os.path.join(self.tmp.name, "settings.json"), "w") as handle:
            json.dump({"rotateSeconds": 45}, handle)
        repo = ConfigRepository(self.tmp.name, {})
        value = repo.stored()
        self.assertEqual(value["version"], 5)
        self.assertEqual(value["general"]["latitude"], 43.5)
        self.assertEqual(value["providers"]["weather"]["precip_probability"], 63)
        self.assertEqual(value["display"]["rotation_seconds"], 45)
        self.assertEqual(value["fallback"]["screen"], "clock_weather")
        self.assertTrue(os.path.exists(repo.path))
        self.assertEqual(os.stat(repo.path).st_mode & 0o777, 0o600)

    def test_environment_overrides_stored_source_credentials(self):
        repo = ConfigRepository(self.tmp.name, {
            "MARQUEE_LATITUDE": "44.1", "MARQUEE_TIMEZONE": "America/Toronto",
            "SONARR_URL": "http://sonarr:8989/", "SONARR_API_KEY": "environment-key"})
        value = repo.effective()
        self.assertEqual(value["general"]["latitude"], 44.1)
        self.assertEqual(value["providers"]["tv"]["url"], "http://sonarr:8989")
        self.assertEqual(value["providers"]["tv"]["api_key"], "environment-key")

    def test_secret_is_masked_and_blank_save_preserves_it(self):
        repo = ConfigRepository(self.tmp.name, {})
        repo.save({"providers": {"tv": {"api_key": "secret"}}})
        self.assertNotIn("api_key", repo.public()["providers"]["tv"])
        self.assertTrue(repo.public()["providers"]["tv"]["api_key_set"])
        repo.save({"providers": {"tv": {"api_key": ""}}})
        self.assertEqual(repo.stored()["providers"]["tv"]["api_key"], "secret")

    def test_invalid_timezone_and_ranges_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "timezone"):
            validate_config({"general": {"timezone": "Toronto-ish"}})
        with self.assertRaisesRegex(ValueError, "precip_probability"):
            validate_config({"providers": {"weather": {"precip_probability": 101}}})

    def test_fallback_configuration_is_typed_and_validated(self):
        value = validate_config({"fallback": {"screen": "ambient",
                                                "rotation_seconds": 18,
                                                "show_artwork": False}})
        self.assertEqual(value["fallback"]["screen"], "ambient")
        self.assertEqual(value["fallback"]["rotation_seconds"], 18)
        self.assertFalse(value["fallback"]["show_artwork"])
        with self.assertRaisesRegex(ValueError, "fallback.screen"):
            validate_config({"fallback": {"screen": "post_event"}})

    def test_cast_ambient_cadence_is_bounded_and_typed(self):
        value = validate_config({"fallback": {"cast_ambient_interval_seconds": "600",
                                                "cast_ambient_duration_seconds": "90"}})
        self.assertEqual(value["fallback"]["cast_ambient_interval_seconds"], 600)
        self.assertEqual(value["fallback"]["cast_ambient_duration_seconds"], 90)
        with self.assertRaisesRegex(ValueError, "cast_ambient_duration_seconds"):
            validate_config({"fallback": {"cast_ambient_interval_seconds": 60,
                                            "cast_ambient_duration_seconds": 61}})


if __name__ == "__main__":
    unittest.main()
