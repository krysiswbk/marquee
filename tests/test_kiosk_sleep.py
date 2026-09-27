import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
import pytest
sys.path.insert(0,str(Path(__file__).parents[1]/'integrations/homeassistant'))
from marquee_kiosk import kiosk_awake
from test_homeassistant_bridge import load_bridge

@pytest.mark.parametrize('state,brightness,expected',[('on',255,True),('on',0,False),('off',255,False),('unavailable',255,False),('on',None,False)])
def test_existing_screen_light_owns_popup_permission(state,brightness,expected):
    app=SimpleNamespace(args={},get_state=lambda *a,**k:{'state':state,'attributes':{'brightness':brightness}})
    assert kiosk_awake(app)==expected

def test_sleep_skips_all_popup_and_context_requests_and_reopens_after_wake():
    module=load_bridge();app=module.MarqueeSources();app.args={};app.marquee='https://marquee';app.kiosk_idle_entity='';app.kiosk_browser='test';app.last_kiosk_context='previous';app.log=Mock();app.call_service=Mock();app.bridge=Mock()
    state={'state':'off','attributes':{'brightness':0}}
    app.get_state=lambda *a,**k:state
    app.check_kiosk({});assert app.last_kiosk_context is None;app.bridge.get.assert_not_called();app.call_service.assert_not_called()
    state.update(state='on',attributes={'brightness':255})
    app.bridge.get.return_value.json.return_value={'householdFocus':{'key':'same-house'}}
    app.check_kiosk({});app.call_service.assert_called_once();assert app.call_service.call_args.kwargs['tag']=='marquee'
    app.check_kiosk({});app.call_service.assert_called_once()

def test_sports_popup_also_respects_sleep_and_uses_its_own_tag():
    from test_mma_bridge import load_bridge as load_sports
    module=load_sports();app=module.MarqueeAmbient();app.args={};app.call_service=Mock();app.log=Mock()
    state={'state':'off','attributes':{'brightness':0}}
    app.get_state=lambda *a,**k:state
    app.show_kiosk_marquee();app.call_service.assert_not_called()
    state.update(state='on',attributes={'brightness':255})
    app.show_kiosk_marquee();app.call_service.assert_called_once();assert app.call_service.call_args.kwargs['tag']=='marquee'
