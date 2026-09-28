import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from cast.marquee.runtime import Runtime


class LoopStop:
    def __init__(self, iterations):
        self.remaining = iterations

    def is_set(self):
        return self.remaining <= 0

    def wait(self, _):
        self.remaining -= 1


class RuntimeReliabilityTests(unittest.TestCase):
    def services(self):
        return SimpleNamespace(
            CURRENT_PLEX={"info": None}, LAST_SESSIONS=[], get_session=Mock(return_value=None),
            explain_error=str, log_err=Mock(), log_ok=Mock(), log_warn=Mock(),
            media_backend=lambda: "plex", best_context=lambda info, *args: info,
            atomic_write=Mock(), JSON_PATH="unused", POLL=5,
            CONFIG_REPOSITORY=SimpleNamespace(effective=lambda: {
                "display": {"secondary_screen_mode": "mirror"}}),
            cast_kiosk_enabled=lambda target: True,
            GARAGE_HUB_IP="garage", GARAGE_STATE={"occupied": True},
            hub_ip=lambda: "main", dashcast_active=Mock(return_value=False),
            garage_dashcast_active=Mock(return_value=False),
            card_ok=lambda *args: True, main_card_poll=lambda: 0,
            CARD_GRACE={"until": 0}, cast_card=Mock(), catt=Mock(), catt_for=Mock())

    def run_cycles(self, runtime, count):
        runtime.initialize = Mock()
        runtime._stop = LoopStop(count)
        runtime.run()

    def test_media_error_clears_payload_immediately_and_recovers(self):
        s = self.services()
        movie = {"title": "Movie", "playing": True}
        s.get_session.side_effect = [movie, OSError("offline"), OSError("offline"), None]
        runtime = Runtime(s)
        with patch("cast.marquee.runtime.time.monotonic", side_effect=[100, 159, 160, 170]):
            self.assertEqual(runtime._poll_media("plex"), movie)
            self.assertIsNone(runtime._poll_media("plex"))
            self.assertTrue(s.CURRENT_PLEX["stale"])
            self.assertIsNone(runtime._poll_media("plex"))
            self.assertIsNone(runtime._poll_media("plex"))
        self.assertFalse(s.CURRENT_PLEX["stale"])
        self.assertIsNone(s.CURRENT_PLEX["error"])
        self.assertIn("last_attempt", s.CURRENT_PLEX)
        self.assertIn("last_success", s.CURRENT_PLEX)
        self.assertEqual(s.log_err.call_count, 1)
        self.assertEqual(s.log_ok.call_count, 1)

    def test_startup_media_error_discards_unverified_cache_and_casts_dashboard(self):
        s = self.services()
        s.CURRENT_PLEX["info"] = {"title": "Old movie"}
        s.LAST_SESSIONS.append({"title": "Old movie"})
        s.get_session.side_effect = OSError("offline")
        s.best_context = lambda info, *args: info or {"title": "Dashboard"}
        self.run_cycles(Runtime(s), 1)
        self.assertIsNone(s.CURRENT_PLEX["info"])
        self.assertEqual(s.LAST_SESSIONS, [])
        self.assertEqual(json.loads(s.atomic_write.call_args.args[1])["title"], "Dashboard")
        self.assertEqual(s.cast_card.call_count, 2)

    def test_main_timeout_does_not_starve_garage_or_polling(self):
        s = self.services()
        s.explain_error = lambda error: "plex poll failed"
        s.dashcast_active.side_effect = TimeoutError("main offline")
        self.run_cycles(Runtime(s), 2)
        self.assertEqual(s.get_session.call_count, 2)
        s.cast_card.assert_called_once_with("garage")
        self.assertIn("main Cast reconciliation", s.log_err.call_args.args[0])
        self.assertNotIn("plex", s.log_err.call_args.args[0])
        self.assertFalse(s.CURRENT_PLEX["stale"])
        s.log_ok.assert_not_called()

    def test_garage_failure_retries_without_starving_main_periodic_check(self):
        s = self.services()
        def cast(target=None):
            if target == "garage":
                raise TimeoutError("garage offline")
        s.cast_card.side_effect = cast
        self.run_cycles(Runtime(s), 7)
        self.assertEqual(s.get_session.call_count, 7)
        self.assertEqual(s.dashcast_active.call_count, 2)
        self.assertEqual(sum(c.args == ("garage",) for c in s.cast_card.call_args_list), 7)
        self.assertIn("garage Cast reconciliation", s.log_err.call_args.args[0])

    def test_periodic_main_failure_retries_next_cycle(self):
        s = self.services()
        s.GARAGE_HUB_IP = ""
        s.dashcast_active.side_effect = [True, TimeoutError("offline"), True]
        self.run_cycles(Runtime(s), 8)
        self.assertEqual(s.dashcast_active.call_count, 3)
        self.assertEqual(s.log_ok.call_count, 1)
        self.assertIn("main Cast reconciliation: recovered", s.log_ok.call_args.args[0])

    def test_failed_stop_retries_until_device_released(self):
        s = self.services()
        s.cast_kiosk_enabled = lambda _: False
        s.GARAGE_HUB_IP = ""
        s.dashcast_active.return_value = False
        s.cast_card.side_effect = [TimeoutError("restore failed"), None]
        self.run_cycles(Runtime(s), 3)
        self.assertEqual(s.cast_card.call_count, 2)
        self.assertIn("main Cast reconciliation: recovered", s.log_ok.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
