import requests
import math
import re
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
    FEELS_LIKE = "sensor.open_meteo_apparent_temperature"
    WEATHER_SUMMARY = "sensor.marquee_weather_summary"
    CLOUD_COVER = "sensor.open_meteo_cloud_cover"
    VISIBILITY = "sensor.open_meteo_visibility"
    MOON_PHASE = "sensor.moon_phase"
    SUN = "sun.sun"
    WEATHER_URL = "http://10.10.9.37:8084/ha-weather"
    GARAGE_OCCUPANCY = "input_boolean.garage_os"
    GARAGE_URL = "http://10.10.9.37:8084/garage-occupancy"
    PRESENCE_URL = "http://10.10.9.37:8084/presence"
    CONTEXT_URL = "http://10.10.9.37:8084/contexts"
    SPORTS = ("sensor.leafs_tracker", "sensor.ufc_tracker", "sensor.pfl_tracker")
    OPENSKY_SENSOR = "opensky"
    OPENSKY_EVENT_TTL = timedelta(minutes=30)
    OPENSKY_CACHE_LIMIT = 32
    KIOSK_BROWSER = "a38e5c41-b99f0451"
    BANDS = ((2, 1), (10, 6), (40, 25), (150, 90),
             (500, 300), (1500, 900), (float("inf"), 2000))

    def initialize(self):
        self.bridge = BridgeSession()
        self.opensky_aircraft = {}
        self.sent_band = None
        self.pending_band = None
        self.pending_handle = None
        self.kiosk_context = None
        self.listen_state(self.lux_changed, self.SENSOR)
        self.listen_state(self.weather_changed, self.WEATHER, attribute="all")
        self.listen_state(self.weather_changed, self.FEELS_LIKE)
        for entity in (self.WEATHER_SUMMARY, self.CLOUD_COVER, self.VISIBILITY,
                       self.MOON_PHASE, self.SUN):
            self.listen_state(self.weather_changed, entity, attribute="all")
        self.listen_state(self.garage_changed, self.GARAGE_OCCUPANCY)
        for entity in ("binary_sensor.bedroom_occupancy", "binary_sensor.living_room_occupancy",
                       "binary_sensor.garage_occupancy", "input_boolean.kris_is_asleep",
                       "input_boolean.magda_is_asleep"):
            self.listen_state(self.presence_changed, entity)
        for entity in self.SPORTS:
            self.listen_state(self.sport_changed, entity, attribute="all")
        self.listen_event(self.opensky_entry, "opensky_entry")
        self.listen_event(self.opensky_exit, "opensky_exit")
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
    def _finite(value, low=None, high=None):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
        if not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high):
            return None
        return value

    def _opensky_is_ours(self, data):
        sensor = str((data or {}).get("sensor", "")).strip().lower()
        return sensor in (self.OPENSKY_SENSOR, "sensor." + self.OPENSKY_SENSOR)

    def _home_coordinates(self):
        state = self.get_state("zone.home", attribute="all") or {}
        attrs = state.get("attributes", {}) if isinstance(state, dict) else {}
        return (self._finite(attrs.get("latitude"), -90, 90),
                self._finite(attrs.get("longitude"), -180, 180))

    @classmethod
    def _aircraft_geometry(cls, home_lat, home_lon, latitude, longitude, altitude):
        """Return entry-time geometry from only HA/OpenSky-supplied facts."""
        home_lat = cls._finite(home_lat, -90, 90)
        home_lon = cls._finite(home_lon, -180, 180)
        latitude = cls._finite(latitude, -90, 90)
        longitude = cls._finite(longitude, -180, 180)
        altitude = cls._finite(altitude, 0, 30000)
        if None in (home_lat, home_lon, latitude, longitude, altitude):
            return None
        earth_radius = 6371000.0
        lat1, lat2 = math.radians(home_lat), math.radians(latitude)
        dlat = lat2 - lat1
        dlon = math.radians(longitude - home_lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        horizontal = earth_radius * 2 * math.atan2(math.sqrt(a), math.sqrt(max(0, 1 - a)))
        bearing = (math.degrees(math.atan2(
            math.sin(dlon) * math.cos(lat2),
            math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon))) + 360) % 360
        # OpenSky supplies altitude and entry coordinates, but not a track or
        # home elevation. This is the defensible entry-time line-of-sight
        # approximation from those supplied values; it is not a live track.
        elevation = math.degrees(math.atan2(altitude, max(horizontal, 1.0)))
        return {"bearing": bearing, "elevation": elevation, "altitude": altitude}

    def _expire_opensky(self, now):
        for key, item in list(getattr(self, "opensky_aircraft", {}).items()):
            if now - item["seen_at"] >= self.OPENSKY_EVENT_TTL.total_seconds():
                self.opensky_aircraft.pop(key, None)

    def _publish_opensky(self):
        try:
            self.publish_weather({})
        except Exception as error:
            self.log(f"Marquee OpenSky event publish failed: {error}", level="WARNING")

    def opensky_entry(self, event_name, data, kwargs):
        if not self._opensky_is_ours(data):
            return
        now = datetime.now(timezone.utc).timestamp()
        self._expire_opensky(now)
        data = data or {}
        icao24 = str(data.get("icao24", "")).strip().lower()
        callsign = str(data.get("callsign") or "").strip()
        key = icao24 or callsign.casefold()
        home_lat, home_lon = self._home_coordinates()
        geometry = self._aircraft_geometry(home_lat, home_lon, data.get("latitude"),
                                           data.get("longitude"), data.get("altitude"))
        if not key or not geometry:
            self.log("Marquee ignored OpenSky entry without usable supplied position", level="WARNING")
            return
        aircraft = {"id": icao24 or callsign[:64], "seen_at": now, **geometry}
        if callsign:
            aircraft["callsign"] = callsign[:32]
        self.opensky_aircraft[key] = aircraft
        while len(self.opensky_aircraft) > self.OPENSKY_CACHE_LIMIT:
            oldest = min(self.opensky_aircraft, key=lambda item: self.opensky_aircraft[item]["seen_at"])
            self.opensky_aircraft.pop(oldest, None)
        self._publish_opensky()

    def opensky_exit(self, event_name, data, kwargs):
        if not self._opensky_is_ours(data):
            return
        data = data or {}
        icao24 = str(data.get("icao24", "")).strip().lower()
        callsign = str(data.get("callsign") or "").strip()
        keys = [icao24, callsign.casefold()]
        if callsign:
            keys.extend(key for key, item in self.opensky_aircraft.items()
                        if str(item.get("callsign", "")).casefold() == callsign.casefold())
        for key in keys:
            if key:
                self.opensky_aircraft.pop(key, None)
        self._publish_opensky()

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

    @staticmethod
    def mma_result_rows(value):
        """Turn Team Tracker's marked prior-bout string into readable results."""
        rows = []
        for item in str(value or "").split(";"):
            item = item.strip()
            if not item:
                continue
            item = re.sub(r"^\d+\.\s*", "", item)
            matchup, separator, finish = item.partition(" (")
            winner_side = "left" if matchup.startswith("*") else "right" if matchup.endswith("*") else ""
            matchup = matchup.strip("* ")
            left, vs, right = matchup.partition(" v. ")
            if not vs:
                rows.append("LAST RESULT · " + item)
                continue
            if not winner_side:
                result = "LAST RESULT · " + matchup
                if separator:
                    result += " · " + finish.rstrip(")")
                rows.append(result)
                continue
            winner, loser = (left, right) if winner_side == "left" else (right, left)
            result = "LAST RESULT · " + winner + " def. " + loser
            if separator:
                result += " · " + finish.rstrip(")")
            rows.append(result)
        return list(reversed(rows[-2:]))

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
                        rows = bullets[:2]
                    if attrs.get("last_play"):
                        rows = self.mma_result_rows(attrs["last_play"]) + rows
                    odds = str(attrs.get("odds") or "").strip()
                    over_under = str(attrs.get("overunder") or "").strip()
                    if odds:
                        rows.append("ODDS · " + odds + (" · O/U " + over_under if over_under else ""))
                elif league == "pfl":
                    if attrs.get("last_play"):
                        rows = self.mma_result_rows(attrs["last_play"])
                    odds = str(attrs.get("odds") or "").strip()
                    over_under = str(attrs.get("overunder") or "").strip()
                    if odds:
                        rows.append("ODDS · " + odds + (" · O/U " + over_under if over_under else ""))
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

    def sky_contract(self):
        """Build optional sky data from the aggregate sensor, then HA fallbacks.

        No astronomy is calculated here. In particular, moon phase never gets
        converted into illumination or a position when those facts are absent.
        """
        aggregate = self.get_state(self.WEATHER_SUMMARY, attribute="all") or {}
        aggregate_attrs = aggregate.get("attributes", {}) if isinstance(aggregate, dict) else {}

        def aggregate_value(*names):
            for name in names:
                value = aggregate_attrs.get(name)
                if value not in (None, "", "unknown", "unavailable"):
                    return value
            return None

        def numeric(value, low=None, high=None):
            try:
                value = float(value)
                if not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high):
                    return None
                return value
            except (TypeError, ValueError):
                return None

        def direct_state(entity):
            state = self.get_state(entity, attribute="all") or {}
            return state if isinstance(state, dict) else {"state": state, "attributes": {}}

        def direct_value(entity, *names):
            state = direct_state(entity)
            attrs = state.get("attributes", {})
            for name in names:
                value = attrs.get(name) if name in attrs else state.get("state") if name == "state" else None
                if value not in (None, "", "unknown", "unavailable"):
                    return value
            return None

        cloud = numeric(aggregate_value("cloud_cover", "clouds", "cloudiness"), 0, 100)
        if cloud is None:
            cloud = numeric(direct_value(self.CLOUD_COVER, "state"), 0, 100)
        visibility = numeric(aggregate_value("visibility", "visibility_m", "visibility_km"), 0, 100000)
        visibility_unit = aggregate_value("visibility_unit")
        visibility_state = direct_state(self.VISIBILITY)
        visibility_unit = visibility_unit or visibility_state.get("attributes", {}).get("unit_of_measurement")
        if visibility is None:
            visibility = numeric(visibility_state.get("state"), 0, 100000)
        phase = aggregate_value("moon_phase", "phase")
        if phase is None:
            phase = direct_value(self.MOON_PHASE, "state")
        sun = direct_state(self.SUN)
        sun_attrs = sun.get("attributes", {})
        sun_elevation = numeric(aggregate_value("sun_elevation", "solar_elevation"), -90, 90)
        if sun_elevation is None:
            sun_elevation = numeric(sun_attrs.get("elevation"), -90, 90)
        sun_azimuth = numeric(aggregate_value("sun_azimuth", "solar_azimuth"), 0, 360)
        if sun_azimuth is None:
            sun_azimuth = numeric(sun_attrs.get("azimuth"), 0, 360)
        sun_state = aggregate_value("sun_is_day", "is_day")
        if isinstance(sun_state, str):
            normalized = sun_state.lower()
            sun_state = (normalized in ("true", "on", "day", "above_horizon")
                          if normalized in ("true", "false", "on", "off", "day", "night",
                                             "above_horizon", "below_horizon") else None)
        if not isinstance(sun_state, bool):
            if sun.get("state") == "above_horizon":
                sun_state = True
            elif sun.get("state") == "below_horizon":
                sun_state = False
            else:
                sun_state = None

        moon = {}
        if phase is not None:
            moon["phase"] = str(phase)[:32]
        # These are intentionally aggregate-only: no supplied HA entity exists
        # for moon geometry/illumination, and phase is not a safe substitute.
        for key, names, bounds in (
                ("illumination", ("moon_illumination", "illumination"), (0, 1)),
                ("elevation", ("moon_elevation",), (-90, 90)),
                ("azimuth", ("moon_azimuth",), (0, 360))):
            value = numeric(aggregate_value(*names), *bounds)
            if value is not None:
                moon[key] = value

        now = datetime.now(timezone.utc).timestamp()
        self._expire_opensky(now)
        aircraft = []
        for item in sorted(getattr(self, "opensky_aircraft", {}).values(),
                           key=lambda value: value["seen_at"], reverse=True):
            aircraft.append({key: item[key] for key in
                             ("id", "callsign", "bearing", "elevation", "altitude")
                             if key in item})

        sky = {"sun": {}}
        if sun_state is not None:
            sky["sun"]["is_day"] = sun_state
        if sun_elevation is not None:
            sky["sun"]["elevation"] = sun_elevation
        if sun_azimuth is not None:
            sky["sun"]["azimuth"] = sun_azimuth
        if cloud is not None:
            sky["cloud_cover"] = cloud
        if visibility is not None:
            sky["visibility"] = visibility
            if visibility_unit:
                sky["visibility_unit"] = str(visibility_unit)[:12]
        if moon:
            sky["moon"] = moon
        if aircraft:
            sky["aircraft"] = aircraft[:12]
        return sky

    def publish_weather(self, kwargs):
        import os
        import time
        state = self.get_state(self.WEATHER, attribute="all") or {}
        attrs = state.get("attributes", {})
        # The weather entity does not reliably expose apparent_temperature.
        # Keep the established payload field, sourced only from the dedicated
        # HA feels-like entity; unavailable/non-numeric state remains null.
        feels_state = self.get_state(self.FEELS_LIKE, attribute="all") or {}
        feels_attrs = feels_state.get("attributes", {}) if isinstance(feels_state, dict) else {}
        feels_like = (feels_state.get("state") if isinstance(feels_state, dict)
                      else feels_state)
        try:
            apparent_temperature = float(feels_like)
            if not math.isfinite(apparent_temperature):
                apparent_temperature = None
        except (TypeError, ValueError):
            apparent_temperature = None
        # The dedicated feels-like sensor can use a different unit from the
        # weather entity. The Marquee weather contract carries one shared
        # temperature_unit, so normalize this value to that unit before send.
        weather_unit = attrs.get("temperature_unit", "°C")
        feels_unit = str(feels_attrs.get("unit_of_measurement", weather_unit)).strip().lower()
        feels_is_f = feels_unit in ("°f", "f", "fahrenheit")
        weather_is_f = str(weather_unit).strip().lower() in ("°f", "f", "fahrenheit")
        if apparent_temperature is not None and feels_is_f != weather_is_f:
            apparent_temperature = ((apparent_temperature - 32) * 5 / 9 if feels_is_f
                                    else apparent_temperature * 9 / 5 + 32)
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
            "temp": attrs.get("temperature"), "temperature_unit": weather_unit,
            "condition": state.get("state", "unavailable"),
            "isDay": self.get_state("sun.sun") == "above_horizon",
            "humidity": attrs.get("humidity"), "wind": attrs.get("wind_speed"),
            "windUnit": attrs.get("wind_speed_unit", "km/h"), "wind_gust": attrs.get("wind_gust_speed"),
            "pressure": attrs.get("pressure"), "pressure_unit": attrs.get("pressure_unit", "hPa"),
            "apparent_temperature": apparent_temperature,
            "sky": self.sky_contract(),
            "precipitation_unit": attrs.get("precipitation_unit", "mm"),
            "snowfall_unit": attrs.get("snowfall_unit", "cm"),
            "observed_at": state.get("last_updated"),
            "forecast_updated": self.weather_forecast_at, **self.weather_forecasts,
        }
        try:
            response = self.bridge.post(self.WEATHER_URL, json=payload, timeout=8)
            response.raise_for_status()
        except requests.RequestException as error:
            self.log(f"Marquee weather publish failed: {error}", level="WARNING")
