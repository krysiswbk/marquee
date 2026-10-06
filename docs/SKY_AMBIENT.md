# Marquee sky ambient contract

The existing `POST /ha-weather` payload may include an optional `sky` object.
Older bridges may omit it; Marquee keeps current clock, weather, calendar,
presence, manual-hold, and kiosk behavior unchanged.

```json
{"sky":{"condition":"partlycloudy","cloud_cover":42,
"sun":{"is_day":true,"elevation":31.2,"azimuth":184.0},
"visibility":18000,
"moon":{"phase":"waxing_gibbous","illumination":0.73,"elevation":18.1,"azimuth":92.0}}}
```

`cloud_cover` is 0–100 and `visibility` is in the source's distance unit
(the current bridge passes the HA sensor value through). Moon `illumination` is 0–1; phase is a supplied
label, not a value Marquee calculates. When only `sensor.moon_phase` exists,
Marquee uses a stable ambient placement and a coarse enum-shaped visual phase;
it does not claim exact position or illumination.

The HA bridge can consume the official OpenSky integration's `opensky_entry`
and `opensky_exit` events for `sensor.opensky`. Entry events supply ICAO24,
callsign, altitude, latitude, and longitude; Marquee derives only the
entry-time bearing and line-of-sight elevation from those facts and the
configured `zone.home` coordinates. It publishes no heading, speed, or live
track. Exit events remove the matching cached aircraft, and entries expire
after 30 minutes as a stale-data guard. The integration remains anonymous and
does not add OpenSky polling or credentials.

Source semantics: [Home Assistant OpenSky documentation](https://www.home-assistant.io/integrations/opensky/)
(Events section).
