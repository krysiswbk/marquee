import unittest
from contextlib import ExitStack
from unittest.mock import patch
from xml.etree import ElementTree as ET

from cast.marquee.services import media


def video(state="paused", session="81", key="34524", device="SHIELD"):
    node = ET.Element("Video", type="episode", sessionKey=session,
                      ratingKey=key, title="Episode", viewOffset="0")
    ET.SubElement(node, "Player", state=state, title=device,
                  machineIdentifier=device)
    ET.SubElement(node, "User", title="Viewer")
    return node


class PlexSessionLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.state = patch.object(media, "PLEX_PAUSED_SINCE", {})
        self.state.start()
        self.addCleanup(self.state.stop)

    def test_powered_off_client_expires_after_five_minutes(self):
        stale = video()
        for now in (0, 5, 299):
            self.assertEqual(media.plex_live_sessions([stale], now=now), [stale])
        for now in (300, 36000):
            self.assertEqual(media.plex_live_sessions([stale], now=now), [])

    def test_resume_restores_immediately_and_next_pause_gets_new_grace(self):
        item = video()
        media.plex_live_sessions([item], now=0)
        self.assertEqual(media.plex_live_sessions([item], now=301), [])
        item.find("Player").set("state", "playing")
        self.assertEqual(media.plex_live_sessions([item], now=302), [item])
        item.find("Player").set("state", "paused")
        self.assertEqual(media.plex_live_sessions([item], now=303), [item])
        self.assertEqual(media.plex_live_sessions([item], now=602), [item])
        self.assertEqual(media.plex_live_sessions([item], now=603), [])

    def test_each_session_has_its_own_deadline(self):
        first, second = video(), video(session="82", device="Bedroom")
        media.plex_live_sessions([first], now=0)
        media.plex_live_sessions([first, second], now=200)
        self.assertEqual(media.plex_live_sessions([first, second], now=301), [second])
        second.find("Player").set("state", "playing")
        self.assertEqual(media.plex_live_sessions([first, second], now=36000), [second])

    def test_stopped_and_ended_never_occupy_display(self):
        self.assertEqual(media.plex_live_sessions(
            [video("stopped"), video("ended", session="82")], now=0), [])

    def test_vanished_session_is_cleaned_up(self):
        item = video()
        media.plex_live_sessions([item], now=0)
        media.plex_live_sessions([], now=301)
        self.assertEqual(media.PLEX_PAUSED_SINCE, {})
        self.assertEqual(media.plex_live_sessions([item], now=302), [item])

    def test_new_item_on_same_player_gets_its_own_deadline(self):
        item = video()
        media.plex_live_sessions([item], now=0)
        item.set("ratingKey", "34525")
        self.assertEqual(media.plex_live_sessions([item], now=301), [item])
        self.assertEqual(len(media.PLEX_PAUSED_SINCE), 1)

    def test_selection_excludes_stale_session_before_rotation(self):
        stale, active = video(), video("playing", session="82", device="Bedroom")
        root = ET.Element("MediaContainer")
        root.extend([stale, active])
        media.plex_live_sessions([stale], server="plex", now=0)
        with ExitStack() as patches:
            for name, value in {
                "load_settings": lambda: {},
                "plex_creds": lambda settings: ("plex", "token"),
                "filter_set": lambda *args: set(),
                "fetch_xml": lambda path: root,
                "content_blocked": lambda *args: False,
                "plex_item_terms": lambda node: [],
                "ENV_USERS": set(), "ENV_DEVICES": set(), "ENV_BLOCK_TAGS": set(),
                "LAST_SESSIONS": [],
                "parse_session": lambda node, position: {
                    "key": node.get("sessionKey"), "position": position},
            }.items():
                patches.enter_context(patch.object(media, name, value, create=True))
            patches.enter_context(patch.object(media.time, "monotonic", return_value=36000))
            result = media.current_session()
            self.assertEqual(result["key"], "82")
            self.assertEqual(result["position"], (1, 1))
            self.assertEqual(result["session"]["activeStreams"], 1)
            self.assertEqual([s["device"] for s in media.LAST_SESSIONS], ["Bedroom"])
            active.find("Player").set("state", "stopped")
            self.assertIsNone(media.current_session())
            self.assertEqual(media.LAST_SESSIONS, [])


if __name__ == "__main__":
    unittest.main()
