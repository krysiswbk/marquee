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

    def test_active_payload_is_authoritative_over_ordinary_ambient_context(self):
        active = {"playing": True, "state": "paused", "title": "Episode",
                  "progress": {"offsetMs": 120, "durationMs": 600}}
        ambient = {"playing": True, "state": "playing", "title": "UFC Fight Night",
                   "key": "ufc:live"}
        with patch.object(http, "CURRENT_PLEX", {"info": active, "stale": False}, create=True), \
                patch.object(http, "best_context", return_value=ambient, create=True) as choose:
            self.assertIs(http.now_playing_payload("kiosk"), active)
        choose.assert_called_once()

    def test_active_playback_wins_over_competing_ambient_context(self):
        plex = {"playing": True, "state": "playing", "title": "2024 Recap",
                "key": "plex:session", "artwork": "/poster.jpg",
                "progress": {"offsetMs": 1200, "durationMs": 6000}}
        ambient = {"playing": True, "type": "media_context", "title": "UFC Fight Night",
                   "key": "ufc:live"}
        with patch.object(http, "CURRENT_PLEX", {"info": plex, "stale": False}, create=True), \
                patch.object(http, "best_context", return_value=ambient, create=True) as choose:
            payload = http.now_playing_payload("kiosk")
        self.assertEqual(payload, plex)
        choose.assert_called_once()

    def test_critical_attention_preempts_active_playback(self):
        plex = {"playing": True, "state": "paused", "title": "2024 Recap",
                "progress": {"offsetMs": 1200, "durationMs": 6000}}
        critical = {"playing": False, "state": "attention", "title": "Water leak",
                    "attention": {"urgency": "CRITICAL"}, "key": "attention:leak"}
        with patch.object(http, "CURRENT_PLEX", {"info": plex, "stale": False}, create=True), \
                patch.object(http, "best_context", return_value=critical, create=True):
            self.assertIs(http.now_playing_payload("kiosk"), critical)

    def test_critical_attention_restoration_returns_to_active_playback(self):
        plex = {"playing": True, "state": "playing", "title": "2024 Recap",
                "progress": {"offsetMs": 2400, "durationMs": 6000}}
        with patch.object(http, "CURRENT_PLEX", {"info": plex, "stale": False}, create=True), \
                patch.object(http, "best_context", return_value=plex, create=True):
            self.assertIs(http.now_playing_payload("kiosk"), plex)

    def test_non_active_media_still_uses_ambient_arbitration(self):
        ambient = {"playing": True, "type": "media_context", "title": "Weather",
                   "key": "weather:current"}
        with patch.object(http, "CURRENT_PLEX", {"info": {"playing": False,
                                                              "state": "stopped"},
                                                   "stale": False}, create=True), \
                patch.object(http, "best_context", return_value=ambient, create=True) as choose:
            payload = http.now_playing_payload("kiosk")
        self.assertIs(payload, ambient)
        choose.assert_called_once()

    def test_explicit_plex_scope_clears_ambient_when_idle(self):
        ambient = {"playing": True, "type": "media_context", "title": "UFC Fight Night"}
        with patch.object(http, "CURRENT_PLEX", {"info": None, "stale": False}, create=True), \
                patch.object(http, "best_context", return_value=ambient, create=True) as choose:
            self.assertEqual(http.now_playing_payload("plex"),
                             {"playing": False, "state": "idle", "availability": "idle"})
        choose.assert_not_called()

    def test_explicit_plex_scope_preserves_playing_paused_and_clears_stopped(self):
        for state in ("playing", "paused"):
            plex = {"playing": True, "state": state, "title": "Episode"}
            with patch.object(http, "CURRENT_PLEX", {"info": plex, "stale": False}, create=True):
                self.assertIs(http.now_playing_payload("plex"), plex)
        for state in ("stopped", "ended"):
            plex = {"playing": True, "state": state, "title": "Old episode"}
            with patch.object(http, "CURRENT_PLEX", {"info": plex, "stale": False}, create=True):
                self.assertEqual(http.now_playing_payload("plex")["state"], "idle")

    def test_explicit_plex_scope_reports_stale_without_identity(self):
        with patch.object(http, "CURRENT_PLEX", {"info": None, "stale": True}, create=True):
            payload = http.now_playing_payload("plex")
        self.assertEqual(payload, {"playing": False, "state": "stale",
                                   "availability": "stale"})


if __name__ == "__main__":
    unittest.main()
