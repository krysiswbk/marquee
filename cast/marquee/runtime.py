"""Application scheduler and Cast reconciliation loop."""
import json
import os
import threading
import time
try:  # The container imports this package as ``marquee``; tests use ``cast.marquee``.
    from marquee.core.presence import PresenceGate
except ModuleNotFoundError:
    from .core.presence import PresenceGate


def secondary_screen_wanted(configured, playing, occupied):
    """Whether the secondary Cast target should currently host Marquee."""
    mode = str(configured or "off").lower()
    return ((mode == "mirror" and playing) or
            (mode == "weather" and occupied) or
            (mode == "off" and playing and occupied))


class Runtime:
    """Own long-running work; HTTP handlers only read its published state."""
    def __init__(self, services):
        self.s = services
        self._stop = threading.Event()
        self._errors = {}
        self._last_media_success = None
        self._presence_gates = {ip: PresenceGate()
                                for ip in getattr(self.s, "PRESENCE_TARGETS", {})}

    def initialize(self):
        s = self.s
        os.makedirs(s.DATA_DIR, exist_ok=True)
        if not s.PAGE_URL:
            raise SystemExit("Missing required environment variables: PAGE_URL")
        backend = s.media_backend()
        ready = all(s.plex_creds()) if backend == "plex" else all(s.emby_creds(backend))
        if not ready:
            names = {"plex": "PLEX_HOST/PLEX_TOKEN", "emby": "EMBY_HOST/EMBY_API_KEY",
                     "jellyfin": "JELLYFIN_HOST/JELLYFIN_API_KEY"}[backend]
            s.log_warn(f"{backend}: no server configured yet — set {names}, or enter "
                       "them on the settings page")
        if not os.path.exists(s.SETTINGS_PATH):
            s.atomic_write(s.SETTINGS_PATH, json.dumps(s.DEFAULT_SETTINGS))
        else:
            # Historical releases wrote this credential-bearing file as 0644.
            # Tighten it in place during migration without changing contents.
            os.chmod(s.SETTINGS_PATH, 0o600)
        config = s.CONFIG_REPOSITORY.effective()
        s.ARBITER.minimum_relevance = config["context_engine"]["minimum_relevance"]
        s.ARBITER.takeovers_enabled = config["context_engine"]["takeovers_enabled"]
        s.ARBITER.post_event_plex_grace_seconds = (
            config["context_engine"]["post_event_plex_grace_minutes"] * 60)
        s.ARBITER.post_event_max_seconds = (
            config["context_engine"]["post_event_minutes"] * 60)
        s.ARBITER.rotation_seconds = config["fallback"]["rotation_seconds"]
        s.ARBITER.fallback_every = config["display"]["live_fallback_every"]
        s.ARBITER.rotate_relevant = config["fallback"]["rotate_relevant"]
        s.ARBITER.single_item_seconds = config["fallback"]["single_item_seconds"]
        s.ARBITER.cast_ambient_interval_seconds = config["fallback"][
            "cast_ambient_interval_seconds"]
        s.ARBITER.cast_ambient_duration_seconds = config["fallback"][
            "cast_ambient_duration_seconds"]
        s.ARBITER.minimum_context_seconds = config["display"]["minimum_context_seconds"]
        s.EVENT_BUS.subscribe("context.selected", lambda event, data:
            print(json.dumps({"event": event, **data}, separators=(",", ":")), flush=True))
        s.EVENT_BUS.subscribe("provider.error", lambda event, data:
            s.log_warn(f"provider {data['provider']} failed: {data['error']}"))
        s.PROVIDER_ENGINE["value"] = s.ContextEngine(
            s.create_providers(config, s.DATA_DIR), event_bus=s.EVENT_BUS)
        s.PROVIDER_ENGINE["value"].tick()
        from .attention.service import AttentionService
        s.ATTENTION["value"] = AttentionService(config, s.DATA_DIR)
        threading.Thread(target=s.serve_web, daemon=True,
                         name="marquee-http").start()
        s.log_ok(f"Marquee {s.VERSION} ready on :{s.SERVE_PORT} "
                 "(card: /image, settings: /, admin: /admin)")
        s.CARD_GRACE["until"] = time.time() + s.CARD_TIMEOUT

    def _failed(self, scope, error):
        message = (self.s.explain_error(error) if scope.endswith(" session poll")
                   else f"{type(error).__name__}: {error}")
        previous, count = self._errors.get(scope, (None, 0))
        self._errors[scope] = (message, count + 1 if message == previous else 1)
        if message != previous:
            self.s.log_err(f"{scope}: {message} — silencing repeats until it changes or clears")

    def _recovered(self, scope):
        previous = self._errors.pop(scope, None)
        if previous:
            self.s.log_ok(f"{scope}: recovered after {previous[1]} failed attempt(s)")

    def _poll_media(self, backend):
        s = self.s
        scope = f"{backend} session poll"
        s.CURRENT_PLEX["last_attempt"] = time.time()
        try:
            info = s.get_session()
        except Exception as error:
            self._failed(scope, error)
            s.CURRENT_PLEX.update(error=s.explain_error(error), stale=True)
            # A failed source is not evidence that the last title is still
            # playing. Clear the authoritative media payload immediately; the
            # API may report an unavailable state, but never stale media.
            s.CURRENT_PLEX["info"] = None
            if hasattr(s, "LAST_SESSIONS"):
                s.LAST_SESSIONS[:] = []
            return s.CURRENT_PLEX["info"]
        self._last_media_success = time.monotonic()
        s.CURRENT_PLEX.update(info=info, last_success=time.time(), error=None, stale=False)
        self._recovered(scope)
        return info

    def _reconcile_main(self, info, playing, modes, last_playing, last_modes, tick):
        s = self.s
        if (playing != last_playing or modes[0] != last_modes[0] or tick % 6 == 0
                or "main Cast reconciliation" in self._errors):
            if not s.hub_ip():
                if playing and playing != last_playing:
                    s.log_warn("no cast device configured — pick one on the "
                               "settings page or set HUB_IP")
            elif not playing:
                # Native Cast mode owns the display between media sessions.
                # Releasing here returns Nest Hubs to Backdrop/another app,
                # which looks like Marquee is intermittently switching to a
                # blank purple screen or a household dashboard. Keep the
                # Marquee clock/weather card mounted and recover it if an
                # external app took over while the display was idle.
                if not s.dashcast_active():
                    print("no active media context -> restoring Marquee idle card",
                          flush=True)
                    s.cast_card()
            else:
                dash = s.dashcast_active()
                ok = s.card_ok(time.time(), s.main_card_poll(),
                               s.CARD_GRACE["until"])
                if not dash or modes[0] != last_modes[0]:
                    print(f"media context active ({(info or {}).get('title', 'Household desk')}) -> casting",
                          flush=True)
                    s.cast_card()
                elif not ok:
                    last = s.main_card_poll()
                    gone = f"{time.time() - last:.0f}s" if last else "ever"
                    s.log_warn("hub claims to be showing but the card has not "
                               f"polled in {gone} -> re-casting")
                    s.cast_card()

    def _reconcile_garage(self, backend, playing, secondary_mode, garage_wanted,
                          modes, last_garage, last_modes):
        s = self.s
        if s.GARAGE_HUB_IP and (garage_wanted != last_garage or modes[1] != last_modes[1]):
            if garage_wanted:
                reason = ("mirroring active context" if secondary_mode == "mirror"
                          else "showing weather fallback" if not playing
                          else f"occupied and {backend} playing")
                print(f"garage {reason} -> casting garage", flush=True)
                s.cast_card(s.GARAGE_HUB_IP)
            elif last_garage:
                print("garage unoccupied or playback idle -> releasing garage",
                      flush=True)
                s.catt_for(s.GARAGE_HUB_IP, "stop")
            elif s.garage_dashcast_active():
                print("garage unoccupied at startup -> releasing stale marquee",
                      flush=True)
                s.catt_for(s.GARAGE_HUB_IP, "stop")

    def _reconcile_presence_targets(self, info, playing, now, last_wanted):
        s = self.s
        wanted = {}
        targets = getattr(s, "PRESENCE_TARGETS", {})
        state = getattr(s, "PRESENCE_STATE", {"rooms": {}})
        for ip in targets:
            observation = state.get("rooms", {}).get(ip)
            gate = self._presence_gates[ip]
            wanted[ip] = gate.update(
                bool(observation and observation.get("eligible")), now,
                bool(observation and observation.get("absoluteVeto")))
            absolute_veto = bool(observation and observation.get("absoluteVeto"))
            held = bool(getattr(s, "manual_cast_hold_active",
                                lambda _target, _now=None: False)(ip, now)
                        and not absolute_veto)
            protected = bool(playing or (info and
                info.get("attention", {}).get("urgency") == "CRITICAL"))
            if wanted[ip] and not last_wanted.get(ip, False):
                s.cast_card(ip)
            elif (not wanted[ip] and not held and not protected and
                  (last_wanted.get(ip, False) or
                   getattr(s, "dashcast_active_for", lambda _target: False)(ip))):
                s.catt_for(ip, "stop")
        return wanted
    def run(self):
        s = self.s
        self.initialize()
        last_playing, last_garage, tick = None, None, 0
        last_presence = {ip: False for ip in getattr(s, "PRESENCE_TARGETS", {})}
        last_modes = [False, False]
        while not self._stop.is_set():
            try:
                backend = s.media_backend()
                plex_info = self._poll_media(backend)
                info = s.best_context(plex_info)
                s.atomic_write(s.JSON_PATH, json.dumps(info or {"playing": False}))
                modes = (s.cast_kiosk_enabled("hubs"), s.cast_kiosk_enabled("garage"))
                playing = bool(info and info.get("playing") is True
                               and not info.get("ambient")) or modes[0]
                secondary_mode = (s.CONFIG_REPOSITORY.effective().get("display", {})
                                  .get("secondary_screen_mode", "off"))
                garage_info = s.best_context(plex_info, "garage")
                garage_attention = bool(garage_info and garage_info.get("attention"))
                presence_configured = bool(getattr(s, "PRESENCE_STATE", {}).get("rooms"))
                garage_wanted = bool(not presence_configured and s.GARAGE_HUB_IP and
                    (garage_attention or (modes[1] and s.GARAGE_STATE["occupied"]) or
                     secondary_screen_wanted(secondary_mode, bool(info),
                                             s.GARAGE_STATE["occupied"])))
                try:
                    if not presence_configured or playing:
                        self._reconcile_main(info, playing, modes, last_playing, last_modes, tick)
                except Exception as error:
                    self._failed("main Cast reconciliation", error)
                else:
                    last_playing, last_modes[0] = playing, modes[0]
                    self._recovered("main Cast reconciliation")
                try:
                    self._reconcile_garage(backend, playing, secondary_mode, garage_wanted,
                                           modes, last_garage, last_modes)
                except Exception as error:
                    self._failed("garage Cast reconciliation", error)
                else:
                    last_garage, last_modes[1] = garage_wanted, modes[1]
                    self._recovered("garage Cast reconciliation")
                try:
                    last_presence = self._reconcile_presence_targets(
                        info, playing, time.time(), last_presence)
                except Exception as error:
                    self._failed("presence Cast reconciliation", error)
                else:
                    self._recovered("presence Cast reconciliation")
                self._recovered("scheduler")
            except Exception as error:
                self._failed("scheduler", error)
            finally:
                tick += 1
            self._stop.wait(s.POLL)

    def stop(self):
        self._stop.set()
        engine = self.s.PROVIDER_ENGINE.get("value")
        if engine:
            engine.close()
        attention = self.s.ATTENTION.get("value")
        if attention:
            attention.close()
