from datetime import datetime, timezone
import unittest

from cast.marquee.services.screen_testing import SAMPLES, forced_context, sample_catalog


NOW = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)


class ScreenTestingTests(unittest.TestCase):
    def test_catalog_has_each_rich_surface(self):
        ids = {item["id"] for item in sample_catalog()}
        self.assertTrue({"ufc_live", "nhl_live", "weather", "gaming", "tv",
                         "fallback"} <= ids)

    def test_live_test_is_temporary_and_only_targets_live_kiosk(self):
        value = forced_context(SAMPLES["weather"], "live", 30, NOW)
        self.assertEqual(value["id"], "screen-test:live")
        self.assertEqual(value["priority"], 100)
        self.assertEqual(value["targets"], ["kiosk"])
        self.assertEqual(value["expires"], "2026-09-09T12:00:30+00:00")

    def test_both_test_targets_live_and_cast_without_mutating_fixture(self):
        value = forced_context(SAMPLES["ufc_live"], "both", 120, NOW)
        self.assertEqual(value["targets"], ["kiosk", "hubs"])
        self.assertNotIn("id", SAMPLES["ufc_live"])

    def test_unsafe_duration_is_rejected(self):
        for duration in (0, 9, 1801, "bad"):
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                forced_context(SAMPLES["gaming"], "cast", duration, NOW)

    def test_unknown_destination_is_rejected(self):
        with self.assertRaises(ValueError):
            forced_context(SAMPLES["tv"], "television", 30, NOW)
