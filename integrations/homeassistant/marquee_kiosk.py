"""The existing HA screen light owns whether Marquee may show a kiosk popup."""

def kiosk_awake(app):
    entity = app.args.get('kiosk_screen_entity', 'light.sb2_kiosk_screen')
    value = app.get_state(entity, attribute='all') or {}
    if not isinstance(value, dict) or value.get('state') != 'on':
        return False
    try:
        return float(value.get('attributes', {}).get('brightness', 0)) > 0
    except (TypeError, ValueError):
        return False
