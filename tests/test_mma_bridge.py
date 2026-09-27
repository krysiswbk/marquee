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
