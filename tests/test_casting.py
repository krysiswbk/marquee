import unittest
from unittest.mock import patch

from cast.marquee.core.cast_ambient import calendar_agenda
from cast.marquee.services import media


class CastCalendarAgendaTests(unittest.TestCase):
    def test_ambient_calendar_agenda_is_compact_and_chronological(self):
        contexts = [
            {"id": "calendar:later", "type": "calendar_event", "title": "Dinner",
             "subtitle": "Tomorrow · 6:00 PM", "starts": "2026-09-10T22:00:00+00:00",
             "expires": "2026-09-10T23:00:00+00:00", "priority": 40},
            {"id": "calendar:soon", "type": "calendar_event", "title": "Pickup",
             "subtitle": "Today · 4:00 PM", "starts": "2026-09-09T20:00:00+00:00",
             "expires": "2026-09-09T21:00:00+00:00", "priority": 40},
            {"id": "calendar:urgent", "type": "calendar_event", "title": "Emergency",
             "subtitle": "Now", "starts": "2026-09-09T12:00:00+00:00",
             "expires": "2026-09-09T13:00:00+00:00", "priority": 100,
             "castTakeover": True},
        ]
        agenda = calendar_agenda(contexts)
        self.assertEqual(agenda["id"], "calendar:ambient-agenda")
        self.assertEqual(agenda["rows"], ["Pickup · Today · 4:00 PM", "Dinner · Tomorrow · 6:00 PM"])
        self.assertFalse(agenda["castTakeover"])

    def test_single_calendar_item_and_urgent_takeover_are_not_collapsed(self):
        ordinary = {"id": "calendar:one", "type": "calendar_event", "title": "Pickup"}
        urgent = {"id": "calendar:urgent", "type": "calendar_event", "title": "Now",
                  "priority": 95}
        self.assertIsNone(calendar_agenda([ordinary]))
        self.assertIsNone(calendar_agenda([ordinary, urgent]))

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
