import json
import os
import tempfile
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .model import Context, EventState, parse_time
from .provider import Provider


class WeatherProvider(Provider):
    name = "weather"
    refresh_seconds = 600
    stale_seconds = 1800

    def fetch(self):
        lat, lon = float(self.config["latitude"]), float(self.config["longitude"])
        timezone_name = self.config.get("timezone", "America/Toronto")
        params = urllib.parse.urlencode({
            "latitude": lat, "longitude": lon, "timezone": timezone_name,
            "forecast_days": 2,
            "current": "temperature_2m,precipitation,rain,snowfall,weather_code,wind_gusts_10m",
            "hourly": "precipitation_probability,precipitation,rain,snowfall,weather_code,wind_gusts_10m",
        })
        forecast = self.client.json("https://api.open-meteo.com/v1/forecast?" + params)
        bbox = f"{lon-.45},{lat-.35},{lon+.45},{lat+.35}"
        alerts = self.client.json("https://api.weather.gc.ca/collections/weather-alerts/items?"
                                  + urllib.parse.urlencode({"bbox": bbox, "f": "json", "limit": 25}))
        radar_file = os.path.join(self.data_dir, "provider-assets", "weather-radar.img")
        radar_fresh = os.path.exists(radar_file) and (
            datetime.now().timestamp() - os.path.getmtime(radar_file) < 20 * 60)
        if self.config.get("radar", True) and not radar_fresh:
            _, radar_source = self._radar_url()
            image, mime = self.client.bytes(radar_source, timeout=12)
            if mime == "image/png" and len(image) < 5 * 1024 * 1024:
                asset_dir = os.path.dirname(radar_file)
                os.makedirs(asset_dir, exist_ok=True)
                fd, tmp = tempfile.mkstemp(prefix=".radar-", dir=asset_dir)
                with os.fdopen(fd, "wb") as handle: handle.write(image)
                os.replace(tmp, radar_file)
        snapshot = {}
        try:
            with open(os.path.join(self.data_dir, "ha-weather-context.json")) as handle:
                snapshot = json.load(handle)
        except (OSError, ValueError):
            pass
        return {"forecast": forecast, "alerts": alerts, "snapshot": snapshot}

    def _radar_url(self):
        lat, lon = float(self.config["latitude"]), float(self.config["longitude"])
        span = float(self.config.get("radar_span_degrees", 3.0))
        bbox = f"{lon-span/2},{lat-span/2},{lon+span/2},{lat+span/2}"
        query = urllib.parse.urlencode({
            "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap",
            "LAYERS": "RADAR_1KM_RRAI", "STYLES": "", "SRS": "EPSG:4326",
            "BBOX": bbox, "WIDTH": 1000, "HEIGHT": 700,
            "FORMAT": "image/png", "TRANSPARENT": "FALSE",
        })
        return "/provider-assets/weather-radar.img", "https://geo.weather.gc.ca/geomet?" + query

    def contexts(self, payload, now):
        zone = ZoneInfo(self.config.get("timezone", "America/Toronto"))
        current = payload.get("forecast", {}).get("current", {})
        hourly = payload.get("forecast", {}).get("hourly", {})
        contexts, precip = [], []
        for index, stamp in enumerate(hourly.get("time", [])):
            when = datetime.fromisoformat(stamp).replace(tzinfo=zone).astimezone(now.tzinfo)
            if now <= when <= now + timedelta(hours=6):
                precip.append((when,
                    (hourly.get("precipitation_probability") or [0])[index] or 0,
                    (hourly.get("precipitation") or [0])[index] or 0,
                    (hourly.get("snowfall") or [0])[index] or 0))
        active = float(current.get("precipitation") or 0) > .05
        approaching = next((row for row in precip
                            if row[1] >= self.config.get("precip_probability", 55)
                            and (row[2] >= .1 or row[3] >= .1)), None)
        radar_path, radar_source = self._radar_url()
        alerts = payload.get("alerts", {}).get("features", [])
        for feature in alerts[:3]:
            props = feature.get("properties", {})
            title = (props.get("alert_name_en") or props.get("alert_short_name_en")
                     or props.get("event") or props.get("headline") or "Weather alert")
            severity = str(props.get("risk_colour_en") or props.get("severity") or "Active")
            contexts.append(Context(
                id="weather:alert:" + str(feature.get("id", title)), provider=self.name,
                type="weather", subtype="alert", title=title,
                subtitle=severity + " · Environment Canada",
                body=props.get("alert_text_en") or props.get("description", ""),
                event_state=EventState.LIVE, priority=92, relevance=100, urgency=100,
                significance=90, live=True,
                expires_at=parse_time(props.get("expiration_datetime") or props.get("expires"))
                or now + timedelta(hours=4), refresh_after=now + timedelta(minutes=10),
                artwork_url=radar_path, background_url=radar_path, icon="mdi:alert",
                accent="#ef4444", targets=["kiosk", "hubs"],
                source_url=feature.get("links", [{}])[0].get("href", ""),
                stats=[props.get("feature_name_en") or props.get("areaDesc", ""),
                       props.get("impact_en") or props.get("instruction", "")],
                raw={"radarSource": radar_source, "severity": severity}))
        if active or approaching:
            when = now if active else approaching[0]
            minutes = max(0, round((when - now).total_seconds() / 60))
            snow = float(current.get("snowfall") or 0) > 0 or bool(approaching and approaching[3])
            kind = "Snow" if snow else "Rain"
            state = EventState.LIVE if active else EventState.STARTING_SOON
            title = f"{kind} is active" if active else f"{kind} approaching"
            subtitle = "At the house now" if active else f"Expected in about {minutes} minutes"
            contexts.append(Context(
                id="weather:precipitation", provider=self.name, type="weather",
                subtype="snow" if snow else "rain", title=title, subtitle=subtitle,
                body=payload.get("snapshot", {}).get("summary", "Radar centered on home"),
                start_time=when, event_state=state, priority=87 if active else 84,
                relevance=100, urgency=95 if active else max(55, 100-minutes), significance=65,
                live=active, expires_at=now + timedelta(minutes=75),
                refresh_after=now + timedelta(minutes=10), artwork_url=radar_path,
                background_url=radar_path, icon="mdi:weather-rainy", accent="#4aa3ff",
                targets=["kiosk", "hubs"] if active else ["kiosk"],
                stats=[f"Chance {approaching[1]:.0f}%" if approaching else "Precipitation detected",
                       f"Wind gusts {current.get('wind_gusts_10m', 0)} km/h"],
                raw={"radarSource": radar_source, "etaMinutes": minutes,
                     "current": current, "reason": "active precipitation" if active
                     else "forecast threshold within six-hour window"}))
        gust = float(current.get("wind_gusts_10m") or 0)
        temp = float(current.get("temperature_2m") or 0)
        if gust >= self.config.get("wind_gust_kmh", 70) or temp >= 35 or temp <= -25:
            contexts.append(Context(
                id="weather:extreme", provider=self.name, type="weather", subtype="extreme",
                title="Strong weather conditions", subtitle=f"{temp:.0f}°C · gusts {gust:.0f} km/h",
                event_state=EventState.LIVE, priority=86, relevance=90, urgency=90,
                significance=75, live=True, expires_at=now + timedelta(hours=2),
                targets=["kiosk", "hubs"], artwork_url=radar_path, accent="#f59e0b"))
        self.reason = (f"{len(alerts)} alerts; active precipitation={active}; "
                       f"approaching={'yes, '+str(minutes)+' min' if approaching else 'no'}")
        return contexts
