"""Translate an existing HA weather entity into Marquee's display vocabulary."""
import math
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

CODES = {'sunny': 0, 'clear-night': 0, 'partlycloudy': 2, 'cloudy': 3,
         'fog': 45, 'rainy': 61, 'pouring': 65, 'snowy': 71,
         'snowy-rainy': 73, 'hail': 77, 'lightning': 95, 'lightning-rainy': 95,
         'windy': 2, 'windy-variant': 2}

def number(value):
    if value is None or isinstance(value, bool):
        return None
    value = float(value)
    if not math.isfinite(value):
        raise ValueError('weather value must be finite')
    return value


def precipitation(value, unit, target):
    """Normalize an accumulation to the display unit, or leave it unknown."""
    amount = number(value)
    if amount is None:
        return None
    units = str(unit or '').strip().lower().replace('μ', 'u').replace(' ', '')
    if target == 'mm':
        factor = {'mm': 1, 'millimeter': 1, 'millimeters': 1,
                  'cm': 10, 'centimeter': 10, 'centimeters': 10,
                  'in': 25.4, 'inch': 25.4, 'inches': 25.4}.get(units)
    else:
        factor = {'cm': 1, 'centimeter': 1, 'centimeters': 1,
                  'mm': .1, 'millimeter': .1, 'millimeters': .1,
                  'in': 2.54, 'inch': 2.54, 'inches': 2.54}.get(units)
    if factor is None:
        raise ValueError('unsupported precipitation unit')
    return amount * factor


def first_value(row, *names):
    for name in names:
        if name in row:
            return row.get(name)
    return None

def clean_observation(body):
    if not isinstance(body, dict):
        raise ValueError('expected weather object')
    entity = str(body.get('entity_id', ''))
    if not entity.startswith('weather.'):
        raise ValueError('existing HA weather entity is required')
    condition = str(body.get('condition', 'unavailable'))[:64]
    unit = body.get('temperature_unit', '°C')
    if unit not in ('°C', '°F'):
        raise ValueError('unsupported temperature unit')
    def temp(v):
        n = number(v)
        return (n-32)*5/9 if n is not None and unit == '°F' else n
    wind_unit = body.get('windUnit', 'km/h')
    factor = {'km/h': 1, 'm/s': 3.6, 'mph': 1.609344, 'kn': 1.852}.get(wind_unit)
    if factor is None: raise ValueError('unsupported wind unit')
    pressure_factor = {'hPa': 1, 'mbar': 1, 'Pa': .01, 'kPa': 10, 'inHg': 33.8639}.get(body.get('pressure_unit', 'hPa'))
    def scaled(v, f):
        n=number(v)
        return n*f if n is not None and f is not None else None
    clean = {'entity_id': entity, 'source': 'home_assistant', 'temp': temp(body.get('temp')),
        'condition': condition, 'code': CODES.get(condition),
        'isDay': bool(body.get('isDay', condition != 'clear-night')),
        'humidity': number(body.get('humidity')), 'wind': scaled(body.get('wind'), factor),
        'windUnit': 'km/h', 'pressure': scaled(body.get('pressure'), pressure_factor),
        'apparent_temperature': temp(body.get('apparent_temperature')),
        'wind_gust': scaled(body.get('wind_gust'), factor), 'updated': time.time(),
        'observed_at': str(body.get('observed_at', ''))[:64],
        'forecast_updated': number(body.get('forecast_updated'))}
    if condition in ('unknown', 'unavailable'): clean['temp'] = None
    for typ in ('hourly', 'daily'):
        rows=body.get(typ, [])
        if not isinstance(rows, list) or len(rows)>168: raise ValueError('invalid forecast')
        clean[typ]=[]
        for row in rows:
            stamp=datetime.fromisoformat(row['datetime'])
            if stamp.tzinfo is None: raise ValueError('forecast time needs timezone')
            rain_unit = first_value(row, 'precipitation_unit', 'precipitationUnit') or body.get('precipitation_unit', 'mm')
            snow_unit = first_value(row, 'snowfall_unit', 'snowfallUnit') or body.get('snowfall_unit', 'cm')
            rain = first_value(row, 'precipitation', 'precipitation_amount', 'precipitation_mm')
            snow = first_value(row, 'snowfall', 'snowfall_amount', 'snowfall_cm',
                               'snow_accumulation')
            clean[typ].append({'datetime': stamp.isoformat(), 'condition': str(row.get('condition', ''))[:64],
                'temperature': temp(row.get('temperature')), 'templow': temp(row.get('templow')),
                'precipitation_probability': number(row.get('precipitation_probability')),
                'precipitation': precipitation(rain, rain_unit, 'mm'),
                'precipitation_unit': 'mm',
                'snowfall': precipitation(snow, snow_unit, 'cm'),
                'snowfall_unit': 'cm'})
    return clean

def forecast_payload(obs, timezone_name):
    zone=ZoneInfo(timezone_name)
    current={'temperature_2m': obs.get('temp'), 'weather_code': obs.get('code'),
        'is_day': int(obs.get('isDay', True)), 'relative_humidity_2m': obs.get('humidity'),
        'wind_speed_10m': obs.get('wind'), 'wind_gusts_10m': obs.get('wind_gust'),
        'apparent_temperature': obs.get('apparent_temperature'),
        'time': datetime.fromtimestamp(obs['updated'], timezone.utc).isoformat()}
    fresh = obs.get('forecast_updated') and 0 <= time.time()-obs['forecast_updated'] < 1800
    hourly=obs.get('hourly', []) if fresh else []
    daily=obs.get('daily', []) if fresh else []
    return {'source': 'home_assistant', 'forecast': {'current': current,
        'updated_at': current['time'],
        'hourly': {'time': [r['datetime'] for r in hourly],
            'temperature_2m': [r.get('temperature') for r in hourly],
            'weather_code': [CODES.get(r.get('condition')) for r in hourly],
            'precipitation_probability': [r.get('precipitation_probability') for r in hourly],
            'precipitation': [r.get('precipitation') for r in hourly],
            'snowfall': [r.get('snowfall') for r in hourly]},
        'daily': {'time': [datetime.fromisoformat(r['datetime']).astimezone(zone).date().isoformat() for r in daily],
            'temperature_2m_max': [r.get('temperature') for r in daily],
            'temperature_2m_min': [r.get('templow') for r in daily],
            'weather_code': [CODES.get(r.get('condition')) for r in daily],
            'precipitation_probability_max': [r.get('precipitation_probability') for r in daily],
            'precipitation': [r.get('precipitation') for r in daily],
            'snowfall': [r.get('snowfall') for r in daily]}}}
