import os
import sys
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

from cast.marquee.core.arbitration import ContextArbiter

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'cast'))
from marquee import composition
from marquee.runtime import Runtime
from marquee.services import media


def test_each_receiver_requires_explicit_opt_in(monkeypatch):
    settings = {}
    monkeypatch.setattr(composition, 'load_settings', lambda: settings)
    assert not composition.cast_kiosk_enabled('hubs')
    settings['castKioskActivity'] = True
    assert composition.cast_kiosk_enabled('hubs')
    assert not composition.cast_kiosk_enabled('garage')
    assert not composition.cast_kiosk_enabled('kiosk')
    settings['castKioskActivity'] = 'false'
    assert not composition.cast_kiosk_enabled('hubs')


def test_opt_in_uses_kiosk_selection_without_kiosk_touch_suppression(monkeypatch):
    settings = {}
    monkeypatch.setattr(composition, 'load_settings', lambda: settings)
    monkeypatch.setattr(composition, 'ATTENTION', {'value': None})
    monkeypatch.setattr(composition, 'PROVIDER_ENGINE', {'value': None})
    monkeypatch.setattr(composition, 'kiosk_interacting', lambda: True)
    monkeypatch.setattr(composition, 'ARBITER', ContextArbiter())
    monkeypatch.setattr(composition, 'saved_contexts', lambda: [
        {'id':'ufc:upcoming','type':'ufc_pre','source':'ufc','title':'Upcoming fight',
         'priority':80,'targets':['kiosk'],'eventState':'UPCOMING'}])
    assert composition.best_context(None, 'hubs') is None
    settings['castKioskActivity'] = True
    assert composition.best_context(None, 'hubs')['key'] == 'ufc:upcoming'
    assert composition.best_context(None, 'garage') is None
    settings['castKioskActivity'] = False
    assert composition.best_context(None, 'hubs') is None


def test_cast_url_tracks_destination_mode_and_reverts(monkeypatch):
    calls=[];enabled=set()
    monkeypatch.setattr(media, 'PAGE_URL', 'http://marquee:8084/image?tpl=street')
    monkeypatch.setattr(media, 'GARAGE_HUB_IP', 'garage')
    monkeypatch.setattr(media, 'hub_ip', lambda:'main')
    monkeypatch.setattr(media, 'cast_kiosk_enabled', lambda display:display in enabled)
    monkeypatch.setattr(media, 'quiet_cast_site', lambda target,url:calls.append((target,url)))
    monkeypatch.setattr(media, 'CARD_GRACE', {'until':0})
    for active in [True,False]:
        enabled.clear()
        if active:enabled.add('hubs')
        media.cast_card('main');media.cast_card('garage')
        main=urlsplit(calls[-2][1]);garage=urlsplit(calls[-1][1])
        assert main.path == ('/kiosk' if active else '/image')
        assert parse_qs(main.query).get('receiver') == (['1'] if active else None)
        assert parse_qs(main.query)['display']==['hubs']
        assert garage.path=='/image' and parse_qs(garage.query)['display']==['garage']
        assert parse_qs(main.query)['tpl']==['street']


def test_runtime_keeps_opted_in_receiver_alive_and_reconciles_mode_changes():
    modes=[(False,False),(True,False),(True,True),(False,False)]
    class Steps:
        index=0
        def is_set(self):return self.index>=len(modes)
        def wait(self,_):self.index+=1
    stop=Steps();calls=[];errors=[]
    s=SimpleNamespace(media_backend=lambda:'plex',get_session=lambda:None,
        CURRENT_PLEX={},best_context=lambda *args:None,atomic_write=lambda *args:None,
        JSON_PATH='unused',cast_kiosk_enabled=lambda d:modes[stop.index][d=='garage'],
        CONFIG_REPOSITORY=SimpleNamespace(effective=lambda:{'display':{'secondary_screen_mode':'off'}}),
        GARAGE_HUB_IP='garage',GARAGE_STATE={'occupied':True},hub_ip=lambda:'main',
        catt=lambda *args:calls.append(('main',*args)),
        catt_for=lambda *args:calls.append(args),dashcast_active=lambda:True,
        garage_dashcast_active=lambda:False,card_ok=lambda *args:True,
        main_card_poll=lambda:0,CARD_GRACE={'until':0},POLL=0,
        cast_card=lambda target=None:calls.append((target or 'main','cast')),
        log_warn=errors.append,log_err=errors.append,log_ok=lambda _:None,
        explain_error=str)
    runtime=Runtime(s);runtime._stop=stop;runtime.initialize=lambda:None
    runtime.run()
    assert not errors
    # Native Cast mode keeps the idle Marquee card mounted. Only active
    # kiosk/garage transitions cast or release a target.
    assert calls==[('main','cast'),('garage','cast'),('garage','stop')]
