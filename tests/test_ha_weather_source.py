import json
import ssl
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from cast.marquee.providers.ha_weather import clean_observation, forecast_payload
from cast.marquee.providers.weather import WeatherProvider
from cast.marquee.api.bridge import authorize


def observation(**overrides):
    return {'entity_id': 'weather.home', 'temp': 23.7, 'condition': 'partlycloudy',
            'humidity': 61, 'wind': 10, 'forecast_updated': time.time(),
            'hourly': [{'datetime': '2026-09-13T00:00:00+00:00', 'temperature': 22,
                        'condition': 'rainy', 'precipitation_probability': 40}], **overrides}


def test_existing_ha_entity_is_only_source(tmp_path):
    clean = clean_observation(observation())
    (tmp_path/'ha-weather.json').write_text(json.dumps(clean))
    network = Mock()
    provider = WeatherProvider({'timezone': 'America/Toronto'}, str(tmp_path), network)
    value = provider.fetch()
    assert value['forecast']['current']['temperature_2m'] == clean['temp'] == 23.7
    assert value['forecast']['hourly']['temperature_2m'] == [22]
    assert 'weather-ha.json' in provider.cache_path
    assert not network.mock_calls


def test_unknown_values_and_unavailable_entity_stay_unknown():
    clean=clean_observation(observation(temp=None, condition='unavailable'))
    value=forecast_payload(clean, 'America/Toronto')
    assert value['forecast']['current']['temperature_2m'] is None
    assert value['forecast']['current']['apparent_temperature'] is None
    assert value['forecast']['daily']['temperature_2m_max'] == []


def test_units_are_normalized_once():
    value=clean_observation(observation(temp=68, temperature_unit='°F', wind=10, windUnit='m/s', pressure=101.5, pressure_unit='kPa'))
    assert value['temp'] == 20
    assert value['wind'] == 36
    assert value['pressure'] == 1015
    assert value['hourly'][0]['temperature'] == pytest.approx(-5.5555555)


def test_stale_forecast_does_not_hide_current_conditions():
    clean=clean_observation(observation(forecast_updated=time.time()-2000))
    value=forecast_payload(clean, 'America/Toronto')['forecast']
    assert value['current']['temperature_2m'] == 23.7
    assert value['hourly']['time'] == []


def test_stale_bridge_never_falls_back_to_external_weather(tmp_path):
    clean=clean_observation(observation())
    clean['updated']=time.time()-2000
    (tmp_path/'ha-weather.json').write_text(json.dumps(clean))
    with pytest.raises(ValueError, match='stale'):
        WeatherProvider({}, str(tmp_path)).fetch()


@pytest.mark.parametrize('changes', [{'temp': float('nan')}, {'entity_id': 'sensor.new_temperature'}, {'hourly': [{'datetime': '2026-09-13T00:00:00'}]}])
def test_invalid_weather_rejected(changes):
    with pytest.raises(ValueError): clean_observation(observation(**changes))


def test_bridge_requires_tls_and_scoped_token(tmp_path):
    folder=tmp_path/'bridge-security';folder.mkdir();(folder/'token').write_text('test-only-token')
    h=SimpleNamespace(path='/ha-weather', headers={'Authorization': 'Bearer test-only-token'}, connection=None, _send=Mock())
    assert not authorize(h, str(tmp_path), 'POST')
    h.connection=Mock(spec=ssl.SSLSocket)
    assert authorize(h, str(tmp_path), 'POST')
    h.headers={}
    assert not authorize(h, str(tmp_path), 'POST')
    h.headers={'Authorization': 'Bearer test-only-token'}
    h.path='/save'
    assert not authorize(h, str(tmp_path), 'POST')
    h.path='/api/attention/bindings'
    assert authorize(h, str(tmp_path), 'GET')
    h.connection=None;h.path='/kiosk'
    assert authorize(h, str(tmp_path), 'GET')
