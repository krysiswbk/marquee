import json
import os
import urllib.parse
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .model import Context, EventState, parse_time
from .provider import Provider


class WeatherProvider(Provider):
    name = "weather"
    refresh_seconds = 60
    stale_seconds = 1800

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cache_path = os.path.join(self.data_dir, "provider-cache", "weather-ha.json")

    def fetch(self):
        # HA is the source of truth. Read its existing weather entity snapshot;
        # no IP geolocation, independent forecast service, or synthetic sensors.
        with open(os.path.join(self.data_dir, "ha-weather.json")) as handle:
            observation = json.load(handle)
        if not 0 <= datetime.now().timestamp() - float(observation.get("updated", 0)) < 1800:
            raise ValueError("Home Assistant weather feed is stale")
        snapshot = {}
        try:
            with open(os.path.join(self.data_dir, "ha-weather-context.json")) as handle:
                snapshot = json.load(handle)
        except (OSError, ValueError):
            pass
        from .ha_weather import forecast_payload
        result = forecast_payload(observation, self.config.get("timezone", "America/Toronto"))
        result["snapshot"] = snapshot
        # Existing HA warning entities remain authoritative too.
        features = []
        if datetime.now().timestamp() - float(snapshot.get("updated", 0)) < 1800:
            for key in ("warnings", "watches", "advisories", "statements"):
                value = snapshot.get(key)
                if value and str(value).lower() not in ("0", "none", "unknown", "unavailable", "no alerts", "no warnings", "no watches", "no advisories", "no statements"):
                    features.append({"id": key, "properties": {"event": str(value), "severity": key}})
        result["alerts"] = {"features": features}
        return result

    def _radar_url(self):
        lat, lon = float(self.config["latitude"]), float(self.config["longitude"])
        span = float(self.config.get("radar_span_degrees", 3.0))
        bbox = f"{lon-span/2},{lat-span/2},{lon+span/2},{lat+span/2}"
        query = urllib.parse.urlencode({
            "SERVICE": "WMS", "VERSION": "1.1.1", "REQUEST": "GetMap",
            "LAYERS": "RADAR_1KM_RRAI", "STYLES": "", "SRS": "EPSG:4326",
            "BBOX": bbox, "WIDTH": 1000, "HEIGHT": 700,
            # Preserve transparency so the display's dark matte shows through;
            # an opaque WMS frame creates the white panel seen on the kiosk.
            "FORMAT": "image/png", "TRANSPARENT": "TRUE",
        })
        return "/provider-assets/weather-radar.img", "https://geo.weather.gc.ca/geomet?" + query

    def contexts(self, payload, now):
        zone = ZoneInfo(self.config.get("timezone", "America/Toronto"))
        current = payload.get("forecast", {}).get("current", {})
        hourly = payload.get("forecast", {}).get("hourly", {})
        contexts, precip = [], []
        wind = current.get("wind_speed_10m")
        wind_label = f"Wind {wind:g} km/h" if isinstance(wind, (int, float)) else "Wind unavailable"
        def hourly_value(name, index):
            values = hourly.get(name) or []
            return values[index] if index < len(values) and values[index] is not None else 0
        for index, stamp in enumerate(hourly.get("time", [])):
            when = parse_time(stamp).astimezone(now.tzinfo) if parse_time(stamp) and datetime.fromisoformat(stamp).tzinfo else datetime.fromisoformat(stamp).replace(tzinfo=zone).astimezone(now.tzinfo)
            if now <= when <= now + timedelta(hours=6):
                precip.append((when,
                    hourly_value("precipitation_probability", index),
                    hourly_value("precipitation", index),
                    hourly_value("snowfall", index)))
        active = float(current.get("precipitation") or 0) > .05 or current.get("weather_code") in (61, 63, 65, 71, 73, 75, 95)
        approaching = next((row for row in precip
                            if row[1] >= self.config.get("precip_probability", 55)
                            and (payload.get("source") == "home_assistant" or row[2] >= .1 or row[3] >= .1)), None)
        radar_path, radar_source = self._radar_url()
        radar_file = os.path.join(self.data_dir, "provider-assets", "weather-radar.img")
        try:
            # A stable URL prevents gratuitous GIF restarts; changing it only
            # after the provider atomically replaces the file lets the browser
            # preload and swap a complete new radar product.
            radar_path += f"?v={os.stat(radar_file).st_mtime_ns}"
        except OSError:
            pass
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
            snow = current.get("weather_code") in (71, 73, 75, 77) or float(current.get("snowfall") or 0) > 0 or bool(approaching and approaching[3])
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
                       wind_label],
                raw={"radarSource": radar_source, "etaMinutes": minutes,
                     "current": current, "reason": "active precipitation" if active
                     else "forecast threshold within six-hour window"}))
        gust = float(current.get("wind_gusts_10m") or 0)
        temp = float(current.get("temperature_2m") or 0)
        if gust >= self.config.get("wind_gust_kmh", 70) or temp >= 35 or temp <= -25:
            contexts.append(Context(
                id="weather:extreme", provider=self.name, type="weather", subtype="extreme",
                title="Strong weather conditions", subtitle=f"{temp:.0f}°C · {wind_label}",
                event_state=EventState.LIVE, priority=86, relevance=90, urgency=90,
                significance=75, live=True, expires_at=now + timedelta(hours=2),
                targets=["kiosk", "hubs"], artwork_url=radar_path, accent="#f59e0b"))
        # A valid current observation is useful household data even when it is
        # not urgent. Keep it kiosk-only and low priority: it can share the
        # ambient rotation with Plex/calendar items but can never disturb Cast.
        if current.get("temperature_2m") is not None:
            summary = str(payload.get("snapshot", {}).get("summary", "")).strip()
            contexts.append(Context(
                id="weather:current", provider=self.name, type="weather",
                subtype="current", title="Weather at home",
                subtitle=f"{temp:.0f}°C · {wind_label}",
                body=summary, event_state=EventState.UPCOMING, priority=30,
                relevance=70, urgency=20, significance=35,
                expires_at=now + timedelta(minutes=30),
                refresh_after=now + timedelta(minutes=10), icon="mdi:weather-partly-cloudy",
                accent="#60a5fa", targets=["kiosk"],
                stats=[]))
        self.reason = (f"{len(alerts)} alerts; active precipitation={active}; "
                       f"approaching={'yes, '+str(minutes)+' min' if approaching else 'no'}")
        brief = self.weather_brief(payload, now, active or bool(approaching))
        brief["radar_url"] = radar_path
        brief["radar_enabled"] = bool(self.config.get("radar", True))
        try:
            brief["radar_updated_at"] = os.path.getmtime(radar_file)
        except OSError:
            brief["radar_updated_at"] = None
        for context in contexts:
            context.raw["weather"] = brief
        return contexts

    def weather_brief(self, payload, now, radar_relevant=False):
        """Bounded broadcast data; missing forecast values stay unknown, never zero-filled."""
        forecast = payload.get("forecast", {})
        zone = ZoneInfo(self.config.get("timezone", "America/Toronto"))
        def stamp(value):
            try:
                result = datetime.fromisoformat(value)
                return result if result.tzinfo else result.replace(tzinfo=zone)
            except (ValueError, TypeError):
                return None
        def at(values, index):
            return values[index] if isinstance(values, list) and index < len(values) else None
        hourly = forecast.get("hourly", {})
        hours = []
        for index, value in enumerate(hourly.get("time", [])):
            when = stamp(value)
            if when and now <= when <= now + timedelta(hours=12):
                hours.append({"at": when.isoformat(),
                              "temp": at(hourly.get("temperature_2m"), index),
                              "code": at(hourly.get("weather_code"), index),
                              "is_day": at(hourly.get("is_day"), index),
                              "rain": at(hourly.get("precipitation_probability"), index)})
        daily = forecast.get("daily", {})
        days = []
        for index, value in enumerate(daily.get("time", [])):
            when = stamp(value)
            if when and when.date() >= now.astimezone(zone).date():
                days.append({"date": value, "high": at(daily.get("temperature_2m_max"), index),
                             "low": at(daily.get("temperature_2m_min"), index),
                             "code": at(daily.get("weather_code"), index),
                             "rain": at(daily.get("precipitation_probability_max"), index),
                             "sunrise": (stamp(at(daily.get("sunrise"), index)).isoformat()
                                         if stamp(at(daily.get("sunrise"), index)) else None),
                             "sunset": (stamp(at(daily.get("sunset"), index)).isoformat()
                                        if stamp(at(daily.get("sunset"), index)) else None),
                             "uv": at(daily.get("uv_index_max"), index)})
        current = forecast.get("current", {})
        return {"source": "home_assistant", "timezone": str(zone), "generated_at": forecast.get("updated_at", now.isoformat()),
                "radar_relevant": bool(radar_relevant),
                "observed_at": stamp(current.get("time")).isoformat() if stamp(current.get("time")) else None,
                "current": {key: current.get(key) for key in (
                    "temperature_2m", "apparent_temperature", "relative_humidity_2m", "weather_code",
                    "wind_speed_10m", "wind_gusts_10m", "is_day")},
                "hours": hours[:6], "days": days[:5]}
