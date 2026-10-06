import requests
import math
from marquee_bridge import BridgeSession
from marquee_kiosk import kiosk_awake
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from marquee_presence import bedroom_eligible

import appdaemon.plugins.hass.hassapi as hass


class MarqueeAmbient(hass.Hass):
    SENSOR = "sensor.living_room_motion_sensor_illuminance"
    URL = "http://10.10.9.37:8084/ambient"
    WEATHER = "weather.environment_canada_forecast"
    FEELS_LIKE = "sensor.outside_feels_like_temperature"
    WEATHER_URL = "http://10.10.9.37:8084/ha-weather"
    GARAGE_OCCUPANCY = "input_boolean.garage_os"
    GARAGE_URL = "http://10.10.9.37:8084/garage-occupancy"
    PRESENCE_URL = "http://10.10.9.37:8084/presence"
    CONTEXT_URL = "http://10.10.9.37:8084/contexts"
    SPORTS = ("sensor.leafs_tracker", "sensor.ufc_tracker", "sensor.pfl_tracker")
    KIOSK_BROWSER = "a38e5c41-b99f0451"
    BANDS = ((2, 1), (10, 6), (40, 25), (150, 90),
             (500, 300), (1500, 900), (float("inf"), 2000))

    def initialize(self):
        self.bridge = BridgeSession()
        self.sent_band = None
        self.pending_band = None
        self.pending_handle = None
        self.kiosk_context = None
        self.listen_state(self.lux_changed, self.SENSOR)
        self.listen_state(self.weather_changed, self.WEATHER, attribute="all")
        self.listen_state(self.weather_changed, self.FEELS_LIKE)
        self.listen_state(self.garage_changed, self.GARAGE_OCCUPANCY)
        for entity in ("binary_sensor.bedroom_occupancy", "binary_sensor.living_room_occupancy",
                       "binary_sensor.garage_occupancy", "input_boolean.kris_is_asleep",
                       "input_boolean.magda_is_asleep"):
            self.listen_state(self.presence_changed, entity)
        for entity in self.SPORTS:
            self.listen_state(self.sport_changed, entity, attribute="all")
        self.run_in(self.evaluate, 2)
        self.run_in(self.publish_weather, 3)
        self.run_every(self.publish_weather, "now+60", 60)
        self.weather_forecasts = {}
        self.weather_forecast_at = 0
        self.run_in(self.publish_garage, 4)
        self.run_in(self.publish_presence, 4)
        self.run_every(self.publish_presence, "now+30", 30)
        self.run_in(self.publish_sports, 5)
        self.run_every(self.publish_sports, "now+30", 30)

    def sport_changed(self, entity, attribute, old, new, kwargs):
        self.publish_sports({})

    @staticmethod
    def event_time(value):
        try:
            value = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            return None

    @classmethod
    def mma_active(cls, state, now):
        phase = str(state.get("state", "")).lower()
        starts = cls.event_time(state.get("attributes", {}).get("date"))
        return phase == "in" or bool(phase == "pre" and starts and
            now - timedelta(hours=9) <= starts <= now + timedelta(hours=2))

    @classmethod
    def preferred_mma(cls, states, now):
        # Active/approaching UFC always wins; otherwise show active PFL or
        # the nearest scheduled MMA event on the Team Tracker card.
        for league in ("ufc", "pfl"):
            if cls.mma_active(states.get("sensor." + league + "_tracker", {}), now):
                return league
        upcoming = []
        for league in ("ufc", "pfl"):
            state = states.get("sensor." + league + "_tracker", {})
            starts = cls.event_time(state.get("attributes", {}).get("date"))
            if str(state.get("state", "")).lower() == "pre" and starts and starts >= now:
                upcoming.append((starts, 0 if league == "ufc" else 1, league))
        return min(upcoming)[2] if upcoming else "none"

    def publish_sports(self, kwargs):
        kiosk_candidates = []
        now = datetime.now(timezone.utc)
        states = {entity: self.get_state(entity, attribute="all") or {} for entity in self.SPORTS}
        preferred = self.preferred_mma(states, now)
        self.set_state("sensor.marquee_mma_priority", state=preferred,
                       attributes={"friendly_name": "Marquee MMA priority", "icon": "mdi:boxing-glove"})
        ufc_active = self.mma_active(states.get("sensor.ufc_tracker", {}), now)
        for entity in self.SPORTS:
            state = states[entity]
            attrs = state.get("attributes", {})
            phase = str(state.get("state", attrs.get("state", ""))).lower()
            starts = self.event_time(attrs.get("date"))
            # Replace a formerly-active context with a one-second tombstone.
            relevant = phase in ("in", "post") or (starts and now - timedelta(hours=3)
                        <= starts <= now + timedelta(hours=24))
            if not relevant:
                payload = {"id": "ha:" + entity, "source": "home_assistant",
                           "priority": 0, "type": "expired", "title": "",
                           "targets": ["kiosk"],
                           "expires": (now + timedelta(seconds=1)).isoformat()}
            else:
                league_path = str(attrs.get("league_path", "")).lower()
                league = league_path if league_path in ("ufc", "pfl") else str(attrs.get("league", "")).lower()
                live = phase == "in"
                priority = 90 if live else (85 if phase == "post" else 80)
                expires = now + (timedelta(hours=3) if phase == "post" else timedelta(hours=9))
                team = {"name": attrs.get("team_long_name") or attrs.get("team_name"),
                        "abbr": attrs.get("team_abbr"), "score": attrs.get("team_score"),
                        "record": attrs.get("team_record"), "logo": attrs.get("team_logo")}
                opponent = {"name": attrs.get("opponent_long_name") or attrs.get("opponent_name"),
                            "abbr": attrs.get("opponent_abbr"),
                            "score": attrs.get("opponent_score"),
                            "record": attrs.get("opponent_record"),
                            "logo": attrs.get("opponent_logo")}
                # Team Tracker exposes country flags as MMA "team" logos. Its
                # richer card derives ESPN's transparent athlete headshot from
                # the competitor id; use that same stable asset here.
                if league in ("ufc", "pfl"):
                    if attrs.get("team_id"):
                        team["logo"] = ("https://a.espncdn.com/i/headshots/mma/players/full/"
                                        + str(attrs["team_id"]) + ".png")
                    if attrs.get("opponent_id"):
                        opponent["logo"] = ("https://a.espncdn.com/i/headshots/mma/players/full/"
                                            + str(attrs["opponent_id"]) + ".png")
                rows = []
                if league == "nhl":
                    shots = (attrs.get("team_shots_on_target"), attrs.get("opponent_shots_on_target"))
                    if any(x is not None for x in shots):
                        rows.append(f"Shots · TOR {shots[0] or 0} — {attrs.get('opponent_abbr', 'OPP')} {shots[1] or 0}")
                    if attrs.get("last_play"):
                        rows.append(str(attrs["last_play"]))
                elif league == "ufc":
                    calendar = self.get_state("calendar.ufc", attribute="all") or {}
                    calendar_attrs = calendar.get("attributes", {})
                    calendar_name = str(calendar_attrs.get("message", "")).lower()
                    tracker_name = str(attrs.get("event_name", "")).lower()
                    if calendar_name and (calendar_name in tracker_name or tracker_name in calendar_name):
                        bullets = [line.lstrip("• ") for line in
                                   str(calendar_attrs.get("description", "")).splitlines()
                                   if line.strip().startswith("•")]
                        rows = bullets[:3]
                status = attrs.get("clock") or ""
                if live and attrs.get("quarter"):
                    status = f"{attrs.get('quarter')} · {status}"
                payload = {
                    "id": "ha:" + entity, "source": league, "type": league + "_" + phase,
                    "eventState": "LIVE" if live else "POST_EVENT" if phase == "post" else
                        "STARTING_SOON" if starts and starts <= now + timedelta(hours=2) else "UPCOMING",
                    "priority": priority, "title": attrs.get("event_name") or attrs.get("league_name"),
                    "subtitle": f"{team.get('name', '')} vs. {opponent.get('name', '')}",
                    "status": status, "detail": " · ".join(filter(None, [attrs.get("venue"), attrs.get("location"), attrs.get("tv_network")])),
                    "left": team, "right": opponent, "rows": rows,
                    "accent": "#1f67b1" if league == "nhl" else "#d4a62c" if league == "pfl" else "#d20a0a",
                    "starts": starts.isoformat() if starts else "",
                    "targets": ["kiosk", "hubs"] if phase in ("in", "post") else ["kiosk"],
                    "expires": expires.isoformat(),
                }
                if not (league == "pfl" and ufc_active):
                    kiosk_candidates.append((priority, payload["id"] + ":" + phase))
            try:
                response = self.bridge.post(self.CONTEXT_URL, json=payload, timeout=5)
                response.raise_for_status()
            except Exception as error:
                self.log(f"Marquee sports publish failed for {entity}: {error}", level="WARNING")
        active = max(kiosk_candidates, default=(0, None))[1]
        if active and active != self.kiosk_context:
            self.show_kiosk_marquee()
        self.kiosk_context = active

    def show_kiosk_marquee(self):
        """Sports must never open above the kiosk's deliberate blackout."""
        if not kiosk_awake(self):
            return
        try:
            self.call_service("browser_mod/popup",
                browser_id=[self.KIOSK_BROWSER], title="Marquee", dismissable=True, tag="marquee",
                initial_style="marquee-fullscreen", style_sequence=["marquee-fullscreen"],
                popup_styles=[{
                    "style": "marquee-fullscreen", "include_styles": ["fullscreen"],
                    "styles": """ha-dialog { --ha-dialog-surface-background:#000; --ha-dialog-border-radius:0!important; --dialog-content-padding:0; --padding-x:0; --padding-y:0; } .container,.content,.content .container { margin:0!important; padding:0!important; height:100%!important; min-height:0!important; } .header,ha-dialog-header { position:absolute!important; inset:max(10px,env(safe-area-inset-top)) max(10px,env(safe-area-inset-right)) auto auto!important; z-index:30; width:56px!important; height:56px!important; min-height:56px!important; padding:0!important; border-radius:50%; background:rgba(0,0,0,.68)!important; pointer-events:auto!important; } .header button,ha-dialog-header button { width:56px!important; height:56px!important; min-width:56px!important; min-height:56px!important; } .title { display:none!important; }"""
                }],
                content={"type": "iframe",
                         "url": "http://10.10.9.37:8084/kiosk?v=20260908-clock5",
                         "card_mod": {"style": "ha-card { border:0; box-shadow:none; }"}})
            self.log("Marquee sports popup sent to main-hall kiosk")
        except Exception as error:
            self.log(f"Marquee kiosk popup failed: {error}", level="WARNING")

    def garage_changed(self, entity, attribute, old, new, kwargs):
        self.publish_garage({})

    def presence_changed(self, entity, attribute, old, new, kwargs):
        self.publish_presence({})

    def publish_presence(self, kwargs):
        """Publish the authoritative room-to-receiver mapping; labels are ignored."""
        now = datetime.now(ZoneInfo("America/Toronto"))
        kris = self.get_state("input_boolean.kris_is_asleep") == "on"
        magda = self.get_state("input_boolean.magda_is_asleep") == "on"
        bedroom = self.get_state("binary_sensor.bedroom_occupancy") == "on"
        living = self.get_state("binary_sensor.living_room_occupancy") == "on"
        garage = self.get_state("binary_sensor.garage_occupancy") == "on"
        payload = {"rooms": {
            "10.10.3.81": {"occupied": bedroom,
                "eligible": bedroom_eligible(bedroom, kris, magda, now.hour, now.minute),
                "absoluteVeto": kris or magda or (now.hour, now.minute) >= (22, 0)},
            "10.10.3.73": {"occupied": living, "eligible": living, "absoluteVeto": False},
            "10.10.3.74": {"occupied": garage, "eligible": garage, "absoluteVeto": False},
        }}
        try:
            response = self.bridge.post(self.PRESENCE_URL, json=payload, timeout=5)
            response.raise_for_status()
            self.log("Marquee Cast presence routing refreshed")
        except Exception as error:
            self.log(f"Marquee Cast presence bridge failed: {error}", level="WARNING")

    def publish_garage(self, kwargs):
        occupied = self.get_state(self.GARAGE_OCCUPANCY) == "on"
        response = self.bridge.post(self.GARAGE_URL,
                                 json={"occupied": occupied}, timeout=5)
        response.raise_for_status()
        self.log(f"Marquee garage occupancy: {occupied}")

    def band_for(self, value):
        lux = max(0.0, float(value))
        for index, (ceiling, representative) in enumerate(self.BANDS):
            if lux <= ceiling:
                return index, representative

    def lux_changed(self, entity, attribute, old, new, kwargs):
        self.evaluate({})

    def evaluate(self, kwargs):
        try:
            band, representative = self.band_for(self.get_state(self.SENSOR))
        except (TypeError, ValueError):
            return
        if band == self.sent_band or band == self.pending_band:
            return
        if self.pending_handle:
            self.cancel_timer(self.pending_handle)
        self.pending_band = band
        self.pending_handle = self.run_in(self.publish, 60, band=band, lux=representative)

    def publish(self, kwargs):
        band = kwargs["band"]
        if self.band_for(self.get_state(self.SENSOR))[0] != band:
            self.pending_band = None
            self.pending_handle = None
            self.evaluate({})
            return
        response = self.bridge.post(self.URL, json={"lux": kwargs["lux"]}, timeout=5)
        response.raise_for_status()
        self.sent_band = band
        self.pending_band = None
        self.pending_handle = None
        self.log(f"Marquee ambient band {band}: {response.text}")

    def weather_changed(self, entity, attribute, old, new, kwargs):
        self.publish_weather({})

    def publish_weather(self, kwargs):
        import os
        import time
        state = self.get_state(self.WEATHER, attribute="all") or {}
        attrs = state.get("attributes", {})
        # The weather entity does not reliably expose apparent_temperature.
        # Keep the established payload field, sourced only from the dedicated
        # HA feels-like entity; unavailable/non-numeric state remains null.
        feels_like = self.get_state(self.FEELS_LIKE)
        try:
            apparent_temperature = float(feels_like)
            if not math.isfinite(apparent_temperature):
                apparent_temperature = None
        except (TypeError, ValueError):
            apparent_temperature = None
        if time.time() - self.weather_forecast_at >= 600:
            try:
                forecasts = {}
                supported = int(attrs.get("supported_features", 0))
                for kind, flag in (("daily", 1), ("hourly", 2)):
                    if not supported & flag:
                        forecasts[kind] = []
                        continue
                    response = requests.post("http://supervisor/core/api/services/weather/get_forecasts?return_response",
                        headers={"Authorization": "Bearer " + os.environ["SUPERVISOR_TOKEN"]},
                        json={"entity_id": self.WEATHER, "type": kind}, timeout=20)
                    response.raise_for_status()
                    forecasts[kind] = response.json()["service_response"][self.WEATHER]["forecast"]
                self.weather_forecasts = forecasts
                self.weather_forecast_at = time.time()
            except Exception as error:
                self.log(f"HA weather forecast unavailable: {error}", level="WARNING")
        payload = {
            "entity_id": self.WEATHER,
            "temp": attrs.get("temperature"), "temperature_unit": attrs.get("temperature_unit", "°C"),
            "condition": state.get("state", "unavailable"),
            "isDay": self.get_state("sun.sun") == "above_horizon",
            "humidity": attrs.get("humidity"), "wind": attrs.get("wind_speed"),
            "windUnit": attrs.get("wind_speed_unit", "km/h"), "wind_gust": attrs.get("wind_gust_speed"),
            "pressure": attrs.get("pressure"), "pressure_unit": attrs.get("pressure_unit", "hPa"),
            "apparent_temperature": apparent_temperature,
            "observed_at": state.get("last_updated"),
            "forecast_updated": self.weather_forecast_at, **self.weather_forecasts,
        }
        try:
            response = self.bridge.post(self.WEATHER_URL, json=payload, timeout=8)
            response.raise_for_status()
        except requests.RequestException as error:
            self.log(f"Marquee weather publish failed: {error}", level="WARNING")
