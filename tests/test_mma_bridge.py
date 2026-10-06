import importlib.util
import sys
import types
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch


def load_bridge():
    fake = types.ModuleType('appdaemon.plugins.hass.hassapi')
    fake.Hass = type('Hass', (), {})
    mods = {name: types.ModuleType(name) for name in ['appdaemon','appdaemon.plugins','appdaemon.plugins.hass']}
    mods['appdaemon.plugins.hass.hassapi'] = fake
    path = Path(__file__).parents[1] / 'integrations/homeassistant/marquee_ambient.py'
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location('mma_bridge', path)
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, mods): spec.loader.exec_module(module)
    return module


class MMABridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.module = load_bridge()

    def test_ufc_wins_overlap_and_pfl_takes_over_afterward(self):
        now = datetime.now(timezone.utc)
        ufc = {'state':'IN','attributes':{'date':now.isoformat()}}
        pfl = {'state':'IN','attributes':{'date':now.isoformat()}}
        states = {'sensor.ufc_tracker':ufc,'sensor.pfl_tracker':pfl}
        select = self.module.MarqueeAmbient.preferred_mma
        self.assertEqual(select(states,now), 'ufc')
        ufc['state']='POST'
        self.assertEqual(select(states,now), 'pfl')
        ufc['state']='PRE'
        ufc['attributes']['date']=(now+timedelta(days=2)).isoformat()
        self.assertEqual(select(states,now), 'pfl')
        ufc['attributes']['date']=(now+timedelta(minutes=30)).isoformat()
        self.assertEqual(select(states,now), 'ufc')

    def test_next_upcoming_event_and_no_data(self):
        now=datetime.now(timezone.utc)
        states={f'sensor.{league}_tracker':{'state':'PRE','attributes':{'date':(now+timedelta(days=days)).isoformat()}}
                for league,days in [('ufc',10),('pfl',3)]}
        select=self.module.MarqueeAmbient.preferred_mma
        self.assertEqual(select(states,now),'pfl')
        self.assertEqual(select({},now),'none')

    def test_custom_pfl_tracker_is_normalized_with_headshots(self):
        now=datetime.now(timezone.utc)
        states={'sensor.pfl_tracker':{'state':'IN','attributes':{
            'league':'XXX','league_path':'pfl','date':now.isoformat(),
            'event_name':'PFL Finals','team_name':'Fighter A','opponent_name':'Fighter B',
            'team_id':'100','opponent_id':'200'}}}
        app=self.module.MarqueeAmbient()
        app.bridge=self.module.requests
        app.get_state=lambda entity,**kwargs:states.get(entity,{})
        app.set_state=Mock();app.show_kiosk_marquee=Mock();app.log=Mock();app.kiosk_context=None
        with patch.object(self.module.requests,'post') as post:
            app.publish_sports({})
            payload=next(c.kwargs['json'] for c in post.call_args_list if c.kwargs['json']['id']=='ha:sensor.pfl_tracker')
        self.assertEqual(payload['source'],'pfl')
        self.assertEqual(payload['type'],'pfl_in')
        self.assertEqual(payload['eventState'],'LIVE')
        self.assertTrue(payload['left']['logo'].endswith('/100.png'))
        self.assertEqual(payload['rows'],[])
        self.assertEqual(app.set_state.call_args.kwargs['state'],'pfl')

    def test_sky_prefers_aggregate_and_omits_unavailable_moon_facts(self):
        app = self.module.MarqueeAmbient()
        states = {
            "sensor.marquee_weather_summary": {"state": "ok", "attributes": {
                "cloud_cover": 38, "visibility": 18000, "moon_phase": "first_quarter"}},
            "sensor.open_meteo_cloud_cover": {"state": "91", "attributes": {}},
            "sensor.open_meteo_visibility": {"state": "5000", "attributes": {"unit_of_measurement": "m"}},
            "sensor.moon_phase": {"state": "waxing_gibbous", "attributes": {}},
            "sun.sun": {"state": "above_horizon", "attributes": {"elevation": 27, "azimuth": 191}},
        }
        app.get_state = lambda entity, **kwargs: states.get(entity, {})
        sky = app.sky_contract()
        self.assertEqual(sky["cloud_cover"], 38)
        self.assertEqual(sky["visibility"], 18000)
        self.assertEqual(sky["visibility_unit"], "m")
        self.assertEqual(sky["moon"]["phase"], "first_quarter")
        self.assertNotIn("illumination", sky["moon"])
        self.assertNotIn("elevation", sky["moon"])
        self.assertNotIn("azimuth", sky["moon"])
        self.assertEqual(sky["sun"]["elevation"], 27)
        self.assertEqual(sky["sun"]["azimuth"], 191)
        self.assertNotIn("aircraft", sky)

    def test_sky_direct_entity_fallbacks_are_used(self):
        app = self.module.MarqueeAmbient()
        states = {
            "sensor.marquee_weather_summary": {"state": "ok", "attributes": {}},
            "sensor.open_meteo_cloud_cover": {"state": "44", "attributes": {}},
            "sensor.open_meteo_visibility": {"state": "12", "attributes": {"unit_of_measurement": "km"}},
            "sensor.moon_phase": {"state": "full_moon", "attributes": {}},
            "sun.sun": {"state": "below_horizon", "attributes": {"elevation": -12, "azimuth": 280}},
        }
        app.get_state = lambda entity, **kwargs: states.get(entity, {})
        sky = app.sky_contract()
        self.assertEqual(sky["cloud_cover"], 44)
        self.assertEqual(sky["visibility"], 12)
        self.assertEqual(sky["visibility_unit"], "km")
        self.assertFalse(sky["sun"]["is_day"])
        self.assertEqual(sky["moon"]["phase"], "full_moon")

    def test_opensky_entry_derives_only_entry_geometry_and_exit_clears(self):
        app = self.module.MarqueeAmbient()
        app.opensky_aircraft = {}
        app.publish_weather = Mock()
        app.get_state = lambda entity, **kwargs: {
            "zone.home": {"attributes": {"latitude": 43.5, "longitude": -79.9}}
        }.get(entity, {})
        app.opensky_entry("opensky_entry", {
            "sensor": "opensky", "icao24": "ABC123", "callsign": "TEST123 ",
            "altitude": 10000, "latitude": 43.5, "longitude": -79.7,
        }, {})
        track = app.opensky_aircraft["abc123"]
        self.assertAlmostEqual(track["bearing"], 90, delta=1)
        self.assertGreater(track["elevation"], 0)
        self.assertEqual(track["altitude"], 10000)
        self.assertNotIn("heading", track)
        self.assertNotIn("speed", track)
        app.opensky_exit("opensky_exit", {"sensor": "opensky", "callsign": "TEST123"}, {})
        self.assertEqual(app.opensky_aircraft, {})
        self.assertEqual(app.publish_weather.call_count, 2)

    def test_opensky_ignores_other_sensor_and_expires_stale_entry(self):
        app = self.module.MarqueeAmbient()
        app.opensky_aircraft = {}
        app.publish_weather = Mock()
        app.get_state = lambda entity, **kwargs: {
            "zone.home": {"attributes": {"latitude": 43.5, "longitude": -79.9}}
        }.get(entity, {})
        payload = {"sensor": "another_opensky", "icao24": "ABC123", "callsign": "TEST123",
                   "altitude": 10000, "latitude": 43.5, "longitude": -79.7}
        app.opensky_entry("opensky_entry", payload, {})
        self.assertEqual(app.opensky_aircraft, {})
        payload["sensor"] = "opensky"
        app.opensky_entry("opensky_entry", payload, {})
        app.opensky_aircraft["abc123"]["seen_at"] -= 31 * 60
        self.assertNotIn("aircraft", app.sky_contract())
        self.assertEqual(app.opensky_aircraft, {})
