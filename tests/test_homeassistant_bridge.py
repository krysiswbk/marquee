import importlib.util
import sys
import types
import unittest
from pathlib import Path


def load_bridge():
    api = types.ModuleType("appdaemon.plugins.hass.hassapi")
    api.Hass = object
    hass = types.ModuleType("appdaemon.plugins.hass")
    hass.hassapi = api
    plugins = types.ModuleType("appdaemon.plugins")
    plugins.hass = hass
    appdaemon = types.ModuleType("appdaemon")
    appdaemon.plugins = plugins
    sys.modules.update({"appdaemon": appdaemon, "appdaemon.plugins": plugins,
                        "appdaemon.plugins.hass": hass,
                        "appdaemon.plugins.hass.hassapi": api})
    path = Path(__file__).parents[1] / "integrations/homeassistant/marquee_sources.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("qa_marquee_sources", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Response:
    def raise_for_status(self):
        return None


class HomeAssistantBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_bridge()

    def app(self):
        app = self.module.MarqueeSources()
        app.bridge = self.module.requests
        app.args = {}
        app.marquee = "http://marquee"
        app.calendar_include_terms = ["birthday", "garbage"]
        app.calendar_exclude_terms = ["workday", "radarr"]
        app.calendar_lookahead_days = 14
        app.household_calendar_handle = None
        app.house_summary_handle = None
        app.log = lambda *args, **kwargs: None
        return app

    def test_household_calendar_allowlist_and_kiosk_only_payload(self):
        app = self.app()
        states = {
            "calendar.birthdays": {"attributes": {"friendly_name": "Family Birthdays"}},
            "calendar.garbage": {"attributes": {"friendly_name": "Garbage Collection"}},
            "calendar.radarr": {"attributes": {"friendly_name": "Radarr"}},
        }
        def all_states(*args, **kwargs):
            self.assertNotIn("attribute", kwargs)
            return states
        app.get_state = all_states
        self.assertEqual([x[0] for x in app.household_calendar_entities()],
                         ["calendar.birthdays", "calendar.garbage"])
        def calendar_service(*args, **kwargs):
            self.assertTrue(kwargs["return_response"])
            self.assertNotIn("return_result", kwargs)
            return {"result": {"response": {kwargs["entity_id"]: {"events": [{
                "summary": "Pickup", "start": "2099-01-02", "end": "2099-01-03"}]}}}}
        app.call_service = calendar_service
        sent = []
        self.module.requests.post = lambda url, **kwargs: sent.append((url, kwargs["json"])) or Response()
        app.publish_household_calendars({})
        self.assertTrue(sent[0][0].endswith("/calendar-events"))
        self.assertTrue(all(event["targets"] == ["kiosk"] for event in sent[0][1]["events"]))

    def test_all_day_game_release_uses_household_timezone(self):
        app = self.app()
        app.args = {"calendar_timezone": "America/Toronto"}
        self.assertEqual(app.calendar_timestamp("2026-09-12"), "2026-09-12T00:00:00-04:00")
        self.assertEqual(app.calendar_timestamp("2026-12-12"), "2026-12-12T00:00:00-05:00")
        self.assertEqual(app.calendar_timestamp("2026-09-12T10:00:00+02:00"), "2026-09-12T10:00:00+02:00")

    def test_desk_opens_once_and_household_attention_foregrounds_it(self):
        from unittest.mock import patch
        app = self.app()
        app.get_state = lambda *args, **kwargs: {"state":"on", "attributes":{"brightness":255}}
        app.kiosk_idle_entity = ""
        app.kiosk_browser = "isolated-browser"
        app.last_kiosk_context = None
        calls = []
        app.call_service = lambda *args, **kwargs: calls.append((args, kwargs))
        class Snapshot:
            value = {"playing": False}
            def json(self):
                return self.value
        response = Snapshot()
        with patch.object(self.module.requests, "get", return_value=response):
            app.check_kiosk({})
            app.check_kiosk({})
            self.assertEqual(len(calls), 1)
            self.assertIn("/kiosk?v=household-desk-", calls[0][1]["content"]["url"])
            response.value = {"playing": False, "householdFocus": {"key": "door:open"}}
            app.check_kiosk({})
            self.assertEqual(len(calls), 2)
            app.check_kiosk({})
            self.assertEqual(len(calls), 2)

    def test_house_summary_is_low_priority_kiosk_only(self):
        app = self.app()
        app.house_summary_entities = {"lock.door": "Front door"}
        app.get_state = lambda entity: "locked"
        sent = []
        self.module.requests.post = lambda url, **kwargs: sent.append(kwargs["json"]) or Response()
        app.publish_house_summary({})
        self.assertEqual(sent[0]["priority"], 20)
        self.assertEqual(sent[0]["targets"], ["kiosk"])
        self.assertEqual(sent[0]["rows"], ["Front door · Locked"])


if __name__ == "__main__":
    unittest.main()
