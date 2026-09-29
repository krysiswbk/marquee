"""Optional AppDaemon bridge: ECCC observations/radar -> Marquee provider cache."""
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import requests
from marquee_bridge import BridgeSession
from marquee_kiosk import kiosk_awake
import appdaemon.plugins.hass.hassapi as hass


class MarqueeSources(hass.Hass):
    def initialize(self):
        self.bridge = BridgeSession()
        self.marquee = self.args.get("marquee_url", "http://marquee:8084").rstrip("/")
        self.radar = self.args.get("radar_entity", "camera.halton_hills_radar")
        self.prefix = self.args.get("sensor_prefix", "sensor.environment_canada_")
        self.kiosk_browser = self.args.get("kiosk_browser", "")
        self.kiosk_idle_entity = self.args.get("kiosk_idle_entity", "sensor.kiosk_idle")
        self.kiosk_idle_seconds = int(self.args.get("kiosk_idle_seconds", 30))
        self.last_kiosk_context = None
        self.listen_state(self.kiosk_display_changed, self.args.get("kiosk_screen_entity", "light.sb2_kiosk_screen"), attribute="all")
        self.release_calendars = [str(item) for item in
                                  self.args.get("game_release_calendars", [])]
        self.release_calendar_terms = [str(item).casefold() for item in
            self.args.get("game_release_calendar_terms", ["game release", "game releases"])]
        self.release_refresh_handle = None
        self.household_calendar_handle = None
        self.house_summary_handle = None
        self.calendar_include_terms = [str(item).casefold() for item in self.args.get(
            "calendar_include_terms", ["birthday", "garbage", "holiday", "maxson", "mkjyyz"])]
        self.calendar_exclude_terms = [str(item).casefold() for item in self.args.get(
            "calendar_exclude_terms", ["bills", "radarr", "sonarr", "workday", "working location", "game release"])]
        self.calendar_lookahead_days = int(self.args.get("calendar_lookahead_days", 21))
        self.house_summary_entities = self.args.get("house_summary_entities", {})
        for suffix in ("current_condition", "summary", "temperature", "humidity",
                       "chance_of_precipitation", "wind_speed", "wind_gust",
                       "warnings", "watches", "advisories", "statements"):
            self.listen_state(self.changed, self.prefix + suffix)
        self.run_in(self.publish, 3)
        self.run_every(self.publish, "now+60", 600)
        # Listen to the calendar domain so newly added matching calendars are
        # picked up without updating AppDaemon config. Publishing still uses a
        # narrow name allowlist and cannot leak household calendars.
        self.listen_state(self.calendar_changed, "calendar")
        self.run_in(self.publish_game_releases, 8)
        self.run_every(self.publish_game_releases, "now+120", 1800)
        self.run_in(self.publish_household_calendars, 12)
        self.run_every(self.publish_household_calendars, "now+180", 900)
        self.run_in(self.publish_house_summary, 15)
        self.run_every(self.publish_house_summary, "now+240", 900)
        for entity in self.house_summary_entities:
            self.listen_state(self.house_summary_changed, entity)
        if self.kiosk_browser:
            if self.kiosk_idle_entity:
                self.listen_state(self.kiosk_activity_changed, self.kiosk_idle_entity)
            self.run_every(self.check_kiosk, "now+10", 30)

    def changed(self, entity, attribute, old, new, kwargs):
        self.publish({})

    def calendar_changed(self, entity, attribute, old, new, kwargs):
        # Google/ICS calendar refreshes often emit several state changes in a
        # burst. Coalesce them so the bridge does not hammer HA or Marquee.
        if self.release_refresh_handle:
            try:
                self.cancel_timer(self.release_refresh_handle)
            except Exception:
                pass
        self.release_refresh_handle = self.run_in(self.publish_game_releases, 5)
        if self.household_calendar_handle:
            try:
                self.cancel_timer(self.household_calendar_handle)
            except Exception:
                pass
        self.household_calendar_handle = self.run_in(self.publish_household_calendars, 8)

    def household_calendar_entities(self):
        calendars = []
        for entity, state in (self.get_state() or {}).items():
            if not str(entity).startswith("calendar."):
                continue
            attributes = state.get("attributes", {}) if isinstance(state, dict) else {}
            label = f"{entity} {attributes.get('friendly_name', '')}".replace("_", " ").casefold()
            if (any(term in label for term in self.calendar_include_terms) and
                    not any(term in label for term in self.calendar_exclude_terms)):
                calendars.append((entity, str(attributes.get("friendly_name") or
                                               entity.removeprefix("calendar.").replace("_", " ")).strip()))
        return calendars

    def publish_household_calendars(self, kwargs):
        """Send sanitized, allowlisted household events to the kiosk-only provider."""
        self.household_calendar_handle = None
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=self.calendar_lookahead_days)
        events, seen = [], set()
        try:
            for entity, calendar_name in self.household_calendar_entities():
                result = self.call_service("calendar/get_events", entity_id=entity,
                    start_date_time=now.isoformat(), end_date_time=end.isoformat(),
                    return_response=True) or {}
                if isinstance(result, dict):
                    if result.get("success") is False:
                        raise RuntimeError(f"Calendar request failed for {entity}")
                    result = result.get("result", result)
                    result = result.get("response", result) if isinstance(result, dict) else {}
                values = result.get(entity, {}).get("events", []) if isinstance(result, dict) else []
                for index, event in enumerate(values):
                    if not isinstance(event, dict):
                        continue
                    summary = str(event.get("summary", "")).strip()
                    start = event.get("start")
                    identity = (entity, str(event.get("uid") or summary).casefold(), str(start))
                    if not summary or not start or identity in seen:
                        continue
                    seen.add(identity)
                    events.append({
                        "uid": str(event.get("uid") or f"{index}:{summary}")[:160],
                        "entity_id": entity, "calendar_name": calendar_name[:100],
                        "summary": summary[:160],
                        "description": str(event.get("description", ""))[:240],
                        "start": start, "end": event.get("end"),
                        "all_day": len(str(start)) == 10,
                        "url": str(event.get("url", ""))[:500],
                        "priority": 40, "targets": ["kiosk"], "accent": "#38bdf8",
                    })
            response = self.bridge.post(self.marquee + "/calendar-events",
                                     json={"events": events}, timeout=8)
            response.raise_for_status()
            self.log(f"Marquee household calendar feed refreshed ({len(events)} events)")
        except Exception as error:
            self.log(f"Marquee household calendar bridge failed: {error}", level="WARNING")

    def house_summary_changed(self, entity, attribute, old, new, kwargs):
        if self.house_summary_handle:
            try:
                self.cancel_timer(self.house_summary_handle)
            except Exception:
                pass
        self.house_summary_handle = self.run_in(self.publish_house_summary, 3)

    def publish_house_summary(self, kwargs):
        """Publish a small, non-sensitive home-at-a-glance card to kiosk only."""
        self.house_summary_handle = None
        rows = []
        for entity, label in self.house_summary_entities.items():
            value = self.get_state(entity)
            if value in (None, "", "unknown", "unavailable"):
                continue
            display_value = self.args.get("house_summary_state_labels", {}).get(
                entity, {}).get(str(value), str(value).replace("_", " ").title())
            rows.append(f"{str(label)[:60]} · {str(display_value)[:80]}")
        if not rows:
            return
        now = datetime.now(timezone.utc)
        payload = {"id": "ha:house-summary", "source": "home-assistant",
                   "priority": 20, "type": "house_summary", "title": "Home at a glance",
                   "subtitle": "Current household status", "rows": rows[:5],
                   "starts": now.isoformat(), "expires": (now + timedelta(minutes=20)).isoformat(),
                   "targets": ["kiosk"], "accent": "#38bdf8", "icon": "mdi:home-heart"}
        try:
            response = self.bridge.post(self.marquee + "/contexts", json=payload, timeout=8)
            response.raise_for_status()
        except Exception as error:
            self.log(f"Marquee house summary bridge failed: {error}", level="WARNING")

    def calendar_timestamp(self, value):
        if not value:
            return None
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(self.args.get("calendar_timezone", "UTC")))
        return parsed.isoformat()

    def publish_game_releases(self, kwargs):
        """Publish only explicitly configured release calendars, never every calendar."""
        self.release_refresh_handle = None
        start = datetime.now(timezone.utc)
        end = start + timedelta(days=int(self.args.get("game_release_lookahead_days", 30)))
        events = []
        try:
            calendars = set(self.release_calendars)
            for entity, state in (self.get_state() or {}).items():
                if not str(entity).startswith("calendar."):
                    continue
                attributes = state.get("attributes", {}) if isinstance(state, dict) else {}
                label = f"{entity} {attributes.get('friendly_name', '')}".replace("_", " ").casefold()
                if any(term in label for term in self.release_calendar_terms):
                    calendars.add(entity)
            for entity in sorted(calendars):
                result = self.call_service("calendar/get_events", entity_id=entity,
                    start_date_time=start.isoformat(), end_date_time=end.isoformat(),
                    return_response=True) or {}
                if isinstance(result, dict):
                    if result.get("success") is False:
                        raise RuntimeError(f"Calendar request failed for {entity}")
                    result = result.get("result", result)
                    result = result.get("response", result) if isinstance(result, dict) else {}
                values = (result.get(entity, {}).get("events", [])
                          if isinstance(result, dict) else [])
                for index, event in enumerate(values):
                    if not isinstance(event, dict):
                        continue
                    events.append({"id": f"{entity}:{index}", "entity_id": entity,
                        "summary": event.get("summary"), "description": event.get("description"),
                        "start": self.calendar_timestamp(event.get("start")),
                        "end": self.calendar_timestamp(event.get("end")),
                        "url": event.get("url")})
            response = self.bridge.post(self.marquee + "/gaming-releases",
                                     json={"events": events}, timeout=8)
            response.raise_for_status()
            self.log(f"Marquee game-release feed refreshed ({len(events)} events)")
        except Exception as error:
            self.log(f"Marquee game-release bridge failed: {error}", level="WARNING")
            # The regular 30-minute refresh remains the backstop; use one
            # short retry for transient HA/Marquee startup or network races.
            if not kwargs.get("retry"):
                self.release_refresh_handle = self.run_in(
                    self.publish_game_releases, 60, retry=True)

    def publish(self, kwargs):
        def state(suffix):
            value = self.get_state(self.prefix + suffix)
            return None if value in (None, "unknown", "unavailable") else value
        payload = {key: state(key) for key in (
            "current_condition", "summary", "temperature", "humidity",
            "chance_of_precipitation", "wind_speed", "wind_gust",
            "warnings", "watches", "advisories", "statements")}
        try:
            response = self.bridge.post(self.marquee + "/weather-context", json=payload, timeout=8)
            response.raise_for_status()
            token = os.environ.get("SUPERVISOR_TOKEN")
            if token:
                image = requests.get("http://supervisor/core/api/camera_proxy/" + self.radar,
                    headers={"Authorization": "Bearer " + token}, timeout=15)
                image.raise_for_status()
                radar = self.bridge.post(self.marquee + "/weather-radar", data=image.content,
                    headers={"Content-Type": image.headers.get("Content-Type", "application/octet-stream")},
                    timeout=15)
                radar.raise_for_status()
            self.log("Marquee Environment Canada context and radar refreshed")
        except Exception as error:
            self.log(f"Marquee weather bridge failed: {error}", level="WARNING")

    def kiosk_activity_changed(self, entity, attribute, old, new, kwargs):
        """Forward activity from the enclosing HA kiosk, before a popup exists."""
        try:
            if float(new) < self.kiosk_idle_seconds:
                self.signal_kiosk_activity(True)
        except (TypeError, ValueError):
            pass

    def kiosk_is_idle(self):
        try:
            return float(self.get_state(self.kiosk_idle_entity)) >= self.kiosk_idle_seconds
        except (TypeError, ValueError):
            # Fail closed: an unavailable signal must not interrupt someone
            # actively using the household dashboard.
            return False

    def signal_kiosk_activity(self, active):
        try:
            response = self.bridge.post(self.marquee + "/kiosk-activity",
                json={"active": bool(active), "source": "home-assistant-kiosk-idle"}, timeout=4)
            response.raise_for_status()
        except Exception as error:
            self.log(f"Marquee kiosk activity signal failed: {error}", level="WARNING")

    def kiosk_display_changed(self, entity, attribute, old, new, kwargs):
        if not kiosk_awake(self):
            self.last_kiosk_context = None

    def check_kiosk(self, kwargs):
        """Open the desk only while HA considers the kiosk screen visible."""
        if not kiosk_awake(self):
            self.last_kiosk_context = None
            return
        try:
            if self.kiosk_idle_entity:
                if not self.kiosk_is_idle():
                    self.signal_kiosk_activity(True)
                    return
                self.signal_kiosk_activity(False)
            data = self.bridge.get(self.marquee + "/now-playing.json?display=kiosk",
                                timeout=6).json()
            focus = data.get("householdFocus") or {}
            key = focus.get("key") or (data.get("key") if data.get("type") == "media_context" else None) or "household-desk"
            if key and key != self.last_kiosk_context:
                self.call_service("browser_mod/popup", browser_id=[self.kiosk_browser],
                    title="Marquee", dismissable=True, tag="marquee",
                    initial_style="marquee-fullscreen", style_sequence=["marquee-fullscreen"],
                    popup_styles=[{"style": "marquee-fullscreen", "include_styles": ["fullscreen"],
                      "styles": "ha-dialog{--ha-dialog-surface-background:#000;--ha-dialog-border-radius:0!important;--dialog-content-padding:0;--padding-x:0;--padding-y:0}.container,.content,.content .container{margin:0!important;padding:0!important;height:100%!important;min-height:0!important}.header,ha-dialog-header{position:absolute!important;inset:max(10px,env(safe-area-inset-top)) max(10px,env(safe-area-inset-right)) auto auto!important;z-index:30;width:56px!important;height:56px!important;min-height:56px!important;padding:0!important;border-radius:50%;background:rgba(0,0,0,.68)!important;pointer-events:auto!important}.header button,ha-dialog-header button{width:56px!important;height:56px!important;min-width:56px!important;min-height:56px!important}.title{display:none!important}"}],
                    content={"type": "iframe", "url": self.marquee + "/kiosk?v=household-desk-2.9.1",
                             "card_mod": {"style":
                             "ha-card { border:0; box-shadow:none; }"}})
                self.log(f"Marquee context {key} sent to kiosk")
            self.last_kiosk_context = key
        except Exception as error:
            self.log(f"Marquee kiosk context check failed: {error}", level="WARNING")
