import unittest
from unittest.mock import patch

from cast.marquee.api import http


class NowPlayingContractTests(unittest.TestCase):
    def test_idle_payload_has_no_media_identity(self):
        with patch.object(http, "CURRENT_PLEX", {"info": None, "stale": False}, create=True), \
                patch.object(http, "best_context", return_value=None, create=True):
            payload = http.now_playing_payload("kiosk")
        self.assertEqual(payload, {"playing": False, "state": "idle",
                                   "availability": "idle"})

    def test_unavailable_payload_never_replays_last_title(self):
        with patch.object(http, "CURRENT_PLEX", {
                "info": None, "stale": True, "error": "redacted"}, create=True), \
                patch.object(http, "best_context", return_value=None, create=True):
            payload = http.now_playing_payload("kiosk")
        self.assertFalse(payload["playing"])
        self.assertEqual(payload["state"], "unavailable")
        self.assertNotIn("title", payload)
        self.assertNotIn("key", payload)

    def test_active_payload_is_authoritative_context(self):
        active = {"playing": True, "state": "paused", "title": "Episode",
                  "progress": {"offsetMs": 120, "durationMs": 600}}
        with patch.object(http, "CURRENT_PLEX", {"info": active, "stale": False}, create=True), \
                patch.object(http, "best_context", return_value=active, create=True):
            self.assertIs(http.now_playing_payload("kiosk"), active)


if __name__ == "__main__":
    unittest.main()
