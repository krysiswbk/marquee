import unittest
from unittest.mock import patch

from cast.marquee.services import media


class Result:
    stdout = "volume_muted: False\n"


class CastingTests(unittest.TestCase):
    def test_quiet_cast_orders_mute_launch_and_restore(self):
        calls = []
        def catt(target, *args):
            calls.append((target, *args))
            return Result()
        with patch.object(media, "catt_for", catt), patch.object(
                media.time, "sleep", lambda delay: calls.append(("sleep", delay))), patch.object(
                media, "CAST_MUTE_SETTLE", .8), patch.object(
                media, "CAST_UNMUTE_DELAY", 2.5):
            media.quiet_cast_site("hub", "http://marquee")
        self.assertEqual(calls, [
            ("hub", "info"), ("hub", "volumemute", "true"), ("sleep", .8),
            ("hub", "cast_site", "http://marquee"), ("sleep", 2.5),
            ("hub", "volumemute", "false")])

    def test_existing_muted_state_is_preserved(self):
        calls = []
        class Muted: stdout = "volume_muted: True\n"
        def catt(target, *args):
            calls.append(args)
            return Muted()
        with patch.object(media, "catt_for", catt), patch.object(media.time, "sleep", lambda _: None):
            media.quiet_cast_site("hub", "url")
        self.assertEqual(calls[-1], ("volumemute", "true"))


if __name__ == "__main__": unittest.main()
