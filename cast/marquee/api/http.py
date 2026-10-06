"""Stable HTTP, SSE, upload, and static-file API for Marquee."""
from http.server import BaseHTTPRequestHandler
from .attention import route as attention_route
from .bridge import authorize


def _active_media_payload(info):
    """Return only a live media session as the now-playing authority.

    Plex's session lifecycle already bounds paused playback through
    ``plex_live_sessions``. Keep both playing and grace-period paused
    sessions authoritative here, while allowing stopped/ended payloads (or a
    cleared provider result) to fall through to ambient arbitration/identity
    clearing.
    """
    if not isinstance(info, dict) or info.get("playing") is not True:
        return None
    if str(info.get("state", "")).lower() in ("stopped", "ended"):
        return None
    return info


def _critical_attention_payload(info):
    """Identify the only attention result allowed to preempt active media."""
    return (isinstance(info, dict) and
            str(info.get("attention", {}).get("urgency", "")).upper() == "CRITICAL")


def now_playing_payload(display):
    """Serialize the one authoritative display state.

    A provider failure clears CURRENT_PLEX.info in the runtime. Keep that
    distinction visible to the browser without ever returning the last title.
    """
    # An explicit Now Playing destination is source-scoped. It must never let
    # ambient arbitration manufacture a playing state when Plex is idle.
    if display == "plex":
        media = _active_media_payload(CURRENT_PLEX.get("info"))
        if media:
            return media
        if CURRENT_PLEX.get("stale"):
            return {"playing": False, "state": "stale", "availability": "stale"}
        return {"playing": False, "state": "idle", "availability": "idle"}

    # Let the attention service observe media and perform its normal selection
    # first. Only a critical result may preempt active playback; ordinary
    # ambient/sports results cannot replace Plex identity, progress, or art.
    media = _active_media_payload(CURRENT_PLEX.get("info"))
    info = best_context(CURRENT_PLEX.get("info"), display)
    if _critical_attention_payload(info):
        return info
    if media:
        return media
    if info:
        return info
    if CURRENT_PLEX.get("stale"):
        return {"playing": False, "state": "unavailable",
                "availability": "unavailable"}
    return {"playing": False, "state": "idle", "availability": "idle"}

class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def _send(self, body, ctype="text/html; charset=utf-8", code=200,
              cache_control="no-store"):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(data)

    def _send_file(self, path, code=200):
        try:
            with open(path, "rb") as f:
                ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
                versioned = bool(query.get("v", [""])[0]) and path.lower().endswith(
                    (".css", ".js", ".svg", ".woff", ".woff2"))
                cache = ("public, max-age=31536000, immutable" if versioned
                         else "no-store")
                self._send(f.read(), ctype, code, cache)
        except Exception:
            self._send("not found", "text/plain", 404)

    def _redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _event_stream(self):
        """Push the winning context to browsers; one lightweight thread/client."""
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        display = query.get("display", ["kiosk"])[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("X-Accel-Buffering", "no")
        self.end_headers()
        previous, heartbeat = None, 0.0
        try:
            while True:
                info = now_playing_payload(display)
                encoded = json.dumps(info, separators=(",", ":"))
                now = time.time()
                if encoded != previous:
                    self.wfile.write(("event: context\ndata: " + encoded + "\n\n").encode())
                    self.wfile.flush()
                    previous, heartbeat = encoded, now
                elif now - heartbeat >= 15:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                    heartbeat = now
                time.sleep(.5)
        except (BrokenPipeError, ConnectionResetError, TimeoutError):
            return

    def do_GET(self):
        if not authorize(self, globals().get("DATA_DIR", "/config"), "GET"):
            return
        if attention_route(self, globals(), "GET"):
            return
        path = self.path.split("?")[0]
        if path == "/api/brain":
            service = ATTENTION.get("value")
            return self._send(json.dumps(service.briefing() if service else {"fresh": False}), "application/json")
        if path == "/events":
            return self._event_stream()
        if path == "/api/display-control":
            best_context(CURRENT_PLEX["info"], "kiosk")
            return self._send(json.dumps(ARBITER.control_state()), "application/json")
        if path == "/api/config":
            return self._send(json.dumps(CONFIG_REPOSITORY.public()), "application/json")
        if path == "/api/screen-test":
            now = datetime.now(timezone.utc)
            engine = PROVIDER_ENGINE["value"]
            candidates = []
            if engine:
                candidates = [c.display_dict() for c in engine.all_contexts(now)]
            active = [c for c in saved_contexts(now)
                      if str(c.get("id", "")).startswith("screen-test:")]
            return self._send(json.dumps({"samples": sample_catalog(),
                                          "candidates": candidates,
                                          "active": active}), "application/json")
        if path == "/settings.json":
            self._send(json.dumps(served_settings()), "application/json")
        elif path == "/live-settings.json":
            self._send(json.dumps(served_settings(load_live_settings())), "application/json")
        elif path == "/ambient.json":
            self._send_file(AMBIENT_PATH)
        elif path == "/ha-weather.json":
            self._send(json.dumps(weather()), "application/json")
        elif path == "/devices":
            self._send(json.dumps(scan_devices("refresh" in self.path)),
                       "application/json")
        elif path == "/env-defaults":
            # Allowlisted container defaults, so the settings page can render a
            # blank field as "inheriting this" rather than "nothing is set".
            self._send(json.dumps(env_defaults()), "application/json")
        elif path == "/weather":
            self._send(json.dumps(weather()), "application/json")
        elif path == "/sessions":
            self._send(json.dumps({"sessions": LAST_SESSIONS}), "application/json")
        elif path == "/contexts":
            now = datetime.now(timezone.utc)
            engine = PROVIDER_ENGINE["value"]
            values = saved_contexts(now)
            if engine:
                values += [c.display_dict() for c in engine.all_contexts(now)]
            browse = {}
            if engine:
                browse = {name: [c.display_dict() for c in contexts]
                          for name, contexts in engine.browse_candidates.items()}
            self._send(json.dumps({"contexts": values, "browse": browse,
                                   "active": max(values, key=lambda c: c.get("priority", 0),
                                                 default=None)}), "application/json")
        elif path == "/providers":
            engine = PROVIDER_ENGINE["value"]
            if "refresh=1" in self.path and engine:
                engine.refresh()
            report = engine.diagnostics() if engine else {"providers": {}, "active": {}}
            matched = [CURRENT_PLEX["info"]] if CURRENT_PLEX["info"] else []
            report["providers"]["plex"] = {
                "provider": "plex", "state": "error" if CURRENT_PLEX.get("error") else "ok",
                "lastFetch": (datetime.fromtimestamp(CURRENT_PLEX["last_attempt"], timezone.utc).isoformat()
                              if CURRENT_PLEX.get("last_attempt") else None),
                "lastSuccess": (datetime.fromtimestamp(CURRENT_PLEX["last_success"], timezone.utc).isoformat()
                                if CURRENT_PLEX.get("last_success") else None), "nextRefresh": None,
                "candidateContexts": len(matched), "eligibleContexts": len(matched),
                "error": CURRENT_PLEX.get("error"), "stale": CURRENT_PLEX.get("stale", False),
                "reason": "active media session poller", "contexts": matched,
            }
            for display in ("kiosk", "hubs"):
                active = best_context(CURRENT_PLEX["info"], display)
                report["active"][display] = ((active or {}).get("context")
                    if (active or {}).get("type") == "media_context"
                    else {"provider": "plex", "title": active.get("title")}
                    if active else None)
            self._send(json.dumps(report),
                       "application/json")
        elif path.startswith("/provider-assets/"):
            name = os.path.basename(urllib.parse.unquote(path))
            asset = os.path.join(DATA_DIR, "provider-assets", name)
            if name == "weather-radar.img":
                try:
                    with open(asset, "rb") as handle:
                        data = handle.read()
                    self._send(data, radar_mime(data[:16]) or "application/octet-stream")
                except OSError:
                    self._send("not found", "text/plain", 404)
            else:
                self._send_file(asset)
        elif path == "/custom-backdrop":
            custom = custom_backdrop_info()
            if not custom:
                self._send("not found", "text/plain", 404)
            else:
                try:
                    with open(custom[0], "rb") as f:
                        self._send(f.read(), custom[1])
                except OSError:
                    self._send("not found", "text/plain", 404)
        elif path == "/now-playing.json":
            # Served explicitly rather than through the static fallthrough so we
            # can timestamp the card's heartbeat -- see card_alive().
            LAST_CARD_POLL["at"] = time.time()
            client = self.client_address[0]
            LAST_CARD_POLL["clients"][client] = LAST_CARD_POLL["at"]
            if LAST_CARD_POLL.get("client") != client:
                LAST_CARD_POLL["client"] = client
                print(f"card client connected from {client}", flush=True)
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            display = query.get("display", ["hubs"])[0]
            self._send(json.dumps(now_playing_payload(display)), "application/json")
        elif path == "/healthz":
            last, now = main_card_poll(), time.time()
            self._send(json.dumps({
                "ok": True, "version": VERSION,
                "mediaPollAgo": (round(time.time() - CURRENT_PLEX["last_attempt"], 1)
                                 if CURRENT_PLEX.get("last_attempt") else None),
                "mediaStale": CURRENT_PLEX.get("stale", False),
                # Seconds since the card actually fetched now-playing.json; null
                # means it has never polled. A number past CARD_TIMEOUT is a Hub
                # showing a dead page.
                "cardPollAgo": round(now - last, 1) if last else None,
                "cardAlive": card_alive(now, last),
                # True while a freshly cast page is still allowed to be silent.
                "cardGrace": now < CARD_GRACE["until"],
                "garageOccupied": GARAGE_STATE["occupied"],
                "garageHubConfigured": bool(GARAGE_HUB_IP),
                "presence": PRESENCE_STATE,
                "kioskInteractionActive": kiosk_interacting(now),
                "kioskActivityAgo": (round(now - KIOSK_ACTIVITY["last"], 1)
                                      if KIOSK_ACTIVITY["last"] else None),
                "kioskActivitySource": KIOSK_ACTIVITY["source"],
            }), "application/json")
        elif path == "/release-notes":
            self._send_file(os.path.join(REPO, "CHANGELOG.md"))
        elif path in ("/", "/settings-preview"):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            tab = query.get("tab", [""])[0]
            if tab in ("design", "casting", "connection", "tutorial", "notes", "about"):
                self._redirect("/settings/layout?profile=cast&tab=" + tab)
            else:
                self._redirect("/settings")
        elif path == "/settings":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            tab = query.get("tab", [""])[0]
            if tab in ("design", "casting", "connection", "tutorial", "notes", "about"):
                self._redirect("/settings/layout?profile=cast&tab=" + tab)
            else:
                self._send_file(os.path.join(REPO, "cast", "settings-control.html"))
        elif path == "/settings/layout":
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            live = query.get("profile", ["cast"])[0] == "live"
            self._send_file(os.path.join(REPO, "cast", "live-layout.html" if live else "cast-layout.html"))
        elif path == "/settings/attention":
            self._send_file(os.path.join(REPO, "cast", "attention-settings.html"))
        elif path == "/settings/tests":
            self._send_file(os.path.join(REPO, "cast", "display-tests.html"))
        elif path == "/live-settings":
            self._redirect("/settings/layout?profile=live")
        elif path == "/admin/tests":
            self._redirect("/settings/tests")
        elif path == "/admin/attention":
            self._redirect("/settings/attention")
        elif path == "/admin/fallback":
            self._redirect("/settings#displays")
        elif path.startswith("/admin/provider/"):
            source = urllib.parse.quote(urllib.parse.unquote(path.rsplit("/", 1)[-1]), safe="")
            self._redirect("/settings?source=" + source + "#content")
        elif path in ("/admin", "/admin/"):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            page = query.get("page", [""])[0]
            if page in ("general", "display", "context_engine"):
                self._redirect("/settings#advanced")
            elif page == "interests":
                self._redirect("/settings?source=interests#content")
            elif page == "fallback":
                self._redirect("/settings#displays")
            else:
                self._redirect("/settings#content")
        elif path in ("/image", "/kiosk", "/live"):
            query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            receiver = path == "/kiosk" and query.get("receiver") == ["1"]
            self._send_file(os.path.join(OUTPUT, "kiosk-receiver.html" if receiver else "index.html"))
        else:
            name = os.path.basename(urllib.parse.unquote(path))  # no traversal
            self._send_file(os.path.join(OUTPUT, name))

    def _upload_custom_backdrop(self):
        """Persist one validated JPEG, PNG, or WebP in the /config volume."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0:
            return self._send(json.dumps({"ok": False, "error": "empty upload"}),
                              "application/json", 400)
        if length > MAX_CUSTOM_BACKDROP_BYTES:
            return self._send(json.dumps({"ok": False,
                                          "error": "image exceeds the 15 MB limit"}),
                              "application/json", 413)
        data = self.rfile.read(length)
        mime = image_mime(data[:16])
        if not mime:
            return self._send(json.dumps({"ok": False,
                                          "error": "use a JPEG, PNG, or WebP image"}),
                              "application/json", 415)
        os.makedirs(DATA_DIR, exist_ok=True)
        atomic_write(CUSTOM_BACKDROP_PATH, data, "wb")
        custom = custom_backdrop_info()
        self._send(json.dumps({"ok": True, "mime": mime,
                               "version": custom[2] if custom else ""}),
                   "application/json")

    def do_POST(self):
        if not authorize(self, globals().get("DATA_DIR", "/config"), "POST"):
            return
        if attention_route(self, globals(), "POST"):
            return
        path = self.path.split("?")[0]
        if path == "/api/display-control":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 1024:
                    raise ValueError("invalid request size")
                body = json.loads(self.rfile.read(length))
                if not isinstance(body, dict):
                    raise ValueError("expected an object")
                best_context(CURRENT_PLEX["info"], "kiosk")
                ARBITER.control(body.get("action"))
                best_context(CURRENT_PLEX["info"], "kiosk")
                return self._send(json.dumps(ARBITER.control_state()), "application/json")
            except (ValueError, TypeError) as exc:
                return self._send(json.dumps({"error": str(exc)}), "application/json", 400)
        if path == "/api/screen-test":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 64 * 1024:
                    raise ValueError("screen test request is invalid")
                body = json.loads(self.rfile.read(length))
                destination = str(body.get("destination", "live"))
                sample_id = str(body.get("sampleId", ""))
                candidate_id = str(body.get("candidateId", ""))
                source = SAMPLES.get(sample_id)
                if candidate_id:
                    engine = PROVIDER_ENGINE["value"]
                    matches = ([c.display_dict() for c in engine.all_contexts()]
                               if engine else [])
                    source = next((c for c in matches if c.get("id") == candidate_id), None)
                if not source:
                    raise ValueError("select an available sample or provider context")
                value = forced_context(source, destination,
                                       body.get("durationSeconds", 120))
                value = clean_context(value, "screen-test")
                target = str(body.get("castTarget", "")).strip()
                cast_result = None
                if destination in ("cast", "both"):
                    displays = {item["ip"]: item for item in scan_devices(True)["devices"]
                                if "audio" not in str(item.get("model", "")).lower()}
                    if target and target not in displays:
                        raise ValueError("castTarget is not a discovered Cast display")
                    target = target or hub_ip()
                    if not target:
                        raise ValueError("select a Cast display")
                # One forced context per destination. Replacing it makes repeated
                # visual testing predictable and never edits provider candidates.
                delete_contexts()
                save_context(value)
                if destination in ("cast", "both"):
                    threading.Thread(target=cast_card, args=(target,), daemon=True,
                                     name="screen-test-cast-" + target.replace(".", "-")).start()
                    cast_result = {"target": target,
                                   "name": displays.get(target, {}).get("name", target)}
                return self._send(json.dumps({"ok": True, "context": value,
                                              "cast": cast_result}),
                                  "application/json", 202 if cast_result else 200)
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/api/cast":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 2048:
                    raise ValueError("cast request body is invalid")
                body = json.loads(self.rfile.read(length))
                target = str(body.get("target", "")).strip()
                displays = {item["ip"]: item for item in scan_devices(True)["devices"]
                            if "audio" not in str(item.get("model", "")).lower()}
                if target not in displays:
                    raise ValueError("target is not a discovered Cast display")
                if not hold_manual_cast(target):
                    return self._send(json.dumps({"ok": False,
                                                  "error": "target is blocked by an absolute presence veto"}),
                                      "application/json", 409)
                # Casting waits through mute -> launch -> restore. Keep that
                # work away from the HTTP request thread used by HA buttons.
                threading.Thread(target=cast_card, args=(target, True), daemon=True,
                                 name="cast-" + target.replace(".", "-")).start()
                return self._send(json.dumps({"ok": True, "target": target,
                                              "name": displays[target]["name"]}),
                                  "application/json", 202)
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/weather-context":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 64 * 1024:
                    raise ValueError("weather context body is invalid")
                body = json.loads(self.rfile.read(length))
                allowed = ("current_condition", "summary", "temperature", "humidity",
                           "chance_of_precipitation", "wind_speed", "wind_gust",
                           "warnings", "watches", "advisories", "statements")
                clean = {key: body.get(key) for key in allowed}
                clean["updated"] = time.time()
                atomic_write(os.path.join(DATA_DIR, "ha-weather-context.json"),
                             json.dumps(clean))
                return self._send(json.dumps({"ok": True}), "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/weather-radar":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 5 * 1024 * 1024:
                    raise ValueError("radar image must be between 1 byte and 5 MB")
                data = self.rfile.read(length)
                mime = radar_mime(data[:16])
                if not mime:
                    raise ValueError("radar image must be GIF, PNG, JPEG, or WebP")
                path_out = os.path.join(DATA_DIR, "provider-assets", "weather-radar.img")
                os.makedirs(os.path.dirname(path_out), exist_ok=True)
                atomic_write(path_out, data, "wb")
                return self._send(json.dumps({"ok": True, "bytes": len(data),
                                              "mime": mime}),
                                  "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/gaming-releases":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 128 * 1024:
                    raise ValueError("gaming release feed is invalid")
                body = json.loads(self.rfile.read(length))
                events = body.get("events", [])
                if not isinstance(events, list) or len(events) > 100:
                    raise ValueError("gaming release events must be a list of at most 100 items")
                allowed = ("id", "entity_id", "summary", "description", "start", "end", "url")
                clean = [{key: item.get(key) for key in allowed}
                         for item in events if isinstance(item, dict)]
                atomic_write(os.path.join(DATA_DIR, "ha-gaming-releases.json"),
                             json.dumps({"updated": time.time(), "events": clean}))
                engine = PROVIDER_ENGINE["value"]
                if engine:
                    engine.refresh("gaming")
                return self._send(json.dumps({"ok": True, "events": len(clean)}),
                                  "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/calendar-events":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 256 * 1024:
                    raise ValueError("calendar event feed is invalid")
                body = json.loads(self.rfile.read(length))
                events = body.get("events", [])
                if not isinstance(events, list) or len(events) > 250:
                    raise ValueError("calendar events must be a list of at most 250 items")
                allowed = ("uid", "entity_id", "calendar_name", "summary", "description",
                           "start", "end", "all_day", "url", "priority", "targets", "accent")
                clean = [{key: item.get(key) for key in allowed}
                         for item in events if isinstance(item, dict)]
                atomic_write(os.path.join(DATA_DIR, "ha-calendar-events.json"),
                             json.dumps({"updated": time.time(), "events": clean}))
                engine = PROVIDER_ENGINE["value"]
                if engine:
                    engine.refresh("calendar")
                return self._send(json.dumps({"ok": True, "events": len(clean)}),
                                  "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/contexts":
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                context = clean_context(body)
                save_context(context)
                return self._send(json.dumps({"ok": True, "context": context}),
                                  "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/garage-occupancy":
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                occupied = body.get("occupied")
                if not isinstance(occupied, bool):
                    raise ValueError("occupied must be true or false")
                GARAGE_STATE.update(occupied=occupied, updated=time.time())
                return self._send(json.dumps({"ok": True, "occupied": occupied}),
                                  "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/presence":
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                rooms = body.get("rooms")
                if not isinstance(rooms, dict):
                    raise ValueError("rooms must be an object")
                clean = {}
                for ip, value in rooms.items():
                    if ip not in PRESENCE_TARGETS or not isinstance(value, dict):
                        raise ValueError("presence contains an unknown display")
                    if not isinstance(value.get("eligible"), bool):
                        raise ValueError("presence eligibility must be boolean")
                    clean[ip] = {"room": PRESENCE_TARGETS[ip],
                                 "occupied": bool(value.get("occupied", False)),
                                 "eligible": value["eligible"],
                                 "absoluteVeto": bool(value.get("absoluteVeto", False))}
                PRESENCE_STATE.update(rooms=clean, updated=time.time())
                GARAGE_STATE.update(occupied=clean.get("10.10.3.74", {}).get("occupied", False),
                                    updated=PRESENCE_STATE["updated"])
                return self._send(json.dumps({"ok": True, "rooms": clean}),
                                  "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/kiosk-activity":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = json.loads(self.rfile.read(length)) if length else {}
                active = body.get("active", True)
                if not isinstance(active, bool):
                    raise ValueError("active must be true or false")
                KIOSK_ACTIVITY["last"] = time.time() if active else 0.0
                KIOSK_ACTIVITY["source"] = str(body.get("source", "browser"))[:40]
                return self._send(json.dumps({"ok": True, "active": active}),
                                  "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/custom-backdrop":
            return self._upload_custom_backdrop()
        if path == "/ambient":
            try:
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                lux = max(0.0, float(body["lux"]))
                # The household sensor reads roughly 300 lux with the evening
                # lights on. Treat that as nighttime, not middling daylight;
                # only open the display up once the room is genuinely bright.
                stops = ((0, .86), (2, .84), (10, .81), (40, .77),
                         (150, .72), (500, .64), (1500, .32), (5000, .18))
                opacity = stops[-1][1]
                for (lo, a), (hi, b) in zip(stops, stops[1:]):
                    if lux <= hi:
                        opacity = a + (b - a) * (lux - lo) / (hi - lo)
                        break
                os.makedirs(DATA_DIR, exist_ok=True)
                atomic_write(AMBIENT_PATH, json.dumps({
                    "lux": round(lux, 1), "opacity": round(opacity, 3),
                    "updated": time.time(),
                }))
                return self._send(json.dumps({"ok": True, "opacity": opacity}),
                                  "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path == "/ha-weather":
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 128 * 1024:
                    raise ValueError("invalid weather payload size")
                body = json.loads(self.rfile.read(length))
                from ..providers.ha_weather import clean_observation
                clean = clean_observation(body)
                os.makedirs(DATA_DIR, exist_ok=True)
                atomic_write(HA_WEATHER_PATH, json.dumps(clean))
                return self._send(json.dumps({"ok": True}), "application/json")
            except Exception as e:
                return self._send(json.dumps({"ok": False, "error": str(e)}),
                                  "application/json", 400)
        if path not in ("/save", "/live-save"):
            return self._send("not found", "text/plain", 404)
        return self._save_settings(path, partial=False)

    @staticmethod
    def _merge_settings_patch(current, incoming):
        """Merge a partial display-profile update without sharing nested maps."""
        result = dict(current)
        for key, value in incoming.items():
            existing = result.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                result[key] = WebHandler._merge_settings_patch(existing, value)
            else:
                # Lists intentionally replace as a unit: a partial preset list,
                # for example, is the caller's complete desired preset list.
                result[key] = value
        return result

    def _save_settings(self, path, partial=False, replace_maps=()):
        try:
            live_profile = path == "/live-save"
            length = int(self.headers.get("Content-Length", "0"))
            if partial and not 0 < length <= 256 * 1024:
                raise ValueError("settings patch body must be 1..262144 bytes")
            body = json.loads(self.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("settings body must be an object")
            saved = load_live_settings() if live_profile else load_settings()
            if partial:
                unknown = sorted(set(body) - set(DEFAULT_SETTINGS))
                if unknown:
                    raise ValueError("unknown settings: " + ", ".join(unknown))
                if live_profile:
                    shared = sorted(set(body) & set(LIVE_SHARED_SETTINGS))
                    if shared:
                        raise ValueError("edit Cast/shared settings instead: " + ", ".join(shared))
                merged = self._merge_settings_patch(saved, body)
                # Editors explicitly replace layout maps when resetting or
                # removing a block. Other partial callers keep recursive merge.
                allowed_maps = {"blockLayout", "blockVisibility", "liveLayout", "liveVisibility"}
                if set(replace_maps) - allowed_maps:
                    raise ValueError("only layout and visibility maps may be replaced")
                for key in replace_maps:
                    if key not in body or not isinstance(body[key], dict):
                        raise ValueError("replacement map must be present: " + key)
                    merged[key] = body[key]
            else:
                # Legacy POST is a full replacement and deliberately retains
                # its old default-based behavior for the existing editors.
                merged = {**DEFAULT_SETTINGS,
                          **{k: v for k, v in body.items() if k in DEFAULT_SETTINGS}}
            # Old-shape imports migrate on the way in too: pre-v1.10 flat
            # blockLayout nests under the incoming template, and old flat
            # show*/backdrop gates fold into blockVisibility — so an ancient
            # export pasted into Import round-trips instead of losing data.
            merged["blockLayout"] = migrate_block_layout(
                merged["blockLayout"], merged.get("template") or "spotlight")
            migrate_show_flags(merged)
            if merged.get("liveTheme") not in ("studio", "afterhours", "dispatch"):
                merged["liveTheme"] = "studio"
            if merged["theme"] not in THEMES:
                merged["theme"] = "amber"
            if merged["template"] not in TEMPLATES:
                merged["template"] = "spotlight"
            if merged["clockFormat"] not in ("12h", "24h"):
                merged["clockFormat"] = "12h"
            if merged["titleFont"] not in TITLE_FONTS:
                merged["titleFont"] = "system"
            if merged["bodyFont"] not in TITLE_FONTS:
                merged["bodyFont"] = "system"
            merged["rotateSeconds"] = clamp_rotate(merged["rotateSeconds"])
            for k in ("plexUsers", "plexDevices", "blockTags", "weatherZip",
                      "plexHost", "embyHost", "jellyfinHost"):
                if not isinstance(merged[k], str):
                    merged[k] = ""
            for k in ("plexHost", "embyHost", "jellyfinHost"):
                merged[k] = merged[k].strip()
            if merged["mediaBackend"] not in ("",) + BACKENDS:
                merged["mediaBackend"] = ""
            # Keys/tokens are write-only: a blank field keeps the stored value
            # (the page never sees it, so it cannot echo it back).
            for k in SECRET_SETTINGS:
                typed = merged[k].strip() if isinstance(merged[k], str) else ""
                merged[k] = typed or saved.get(k, "")
            # Refuse to point the marquee at a backend that has no server
            # configured anywhere — a saved-but-dead backend fails silently.
            chosen = merged["mediaBackend"] or ENV_BACKEND
            if chosen == "plex":
                host, key = plex_creds(merged)
            else:
                host, key = emby_creds(chosen, merged)
            if not (host and key):
                what = "token" if chosen == "plex" else "API key"
                raise ValueError(
                    f"{chosen} backend: enter its server address and {what} "
                    "(or set them in the container)")
            merged["weatherZip"] = merged["weatherZip"].strip()[:10]
            if merged["weatherUnits"] not in ("f", "c"):
                merged["weatherUnits"] = "f"
            merged["showWeather"] = bool(merged["showWeather"])
            merged["weatherFX"] = bool(merged["weatherFX"])
            merged["weatherIntensity"] = clean_intensity(merged["weatherIntensity"])
            if merged["fanartType"] not in FANART_TYPES:
                merged["fanartType"] = "background"
            merged["fanartRotateSeconds"] = clamp_fanart_rotate(merged["fanartRotateSeconds"])
            merged["clockSeconds"] = bool(merged["clockSeconds"])
            if not (isinstance(merged["accent"], str)
                    and (merged["accent"] == "" or ACCENT_RE.match(merged["accent"]))):
                merged["accent"] = ""
            if not (isinstance(merged["hubIp"], str)
                    and (merged["hubIp"] == "" or IP_RE.match(merged["hubIp"]))):
                merged["hubIp"] = ""
            merged["blockLayout"] = clean_block_layout(merged["blockLayout"])
            merged["blockVisibility"] = clean_block_visibility(merged["blockVisibility"])
            merged["presets"] = clean_presets(merged["presets"])
            clean_custom_backdrop_settings(merged)
            clean_display_settings(merged)
            merged["liveVisibility"] = clean_live_visibility(merged.get("liveVisibility"))
            merged["liveLayout"] = clean_live_layout(merged.get("liveLayout"))
            target = LIVE_SETTINGS_PATH if live_profile else SETTINGS_PATH
            stored = ({k: v for k, v in merged.items()
                       if k not in LIVE_SHARED_SETTINGS}
                      if live_profile else merged)
            atomic_write(target, json.dumps(stored))
            result = {"ok": True}
            if partial:
                current = load_live_settings() if live_profile else load_settings()
                result["settings"] = served_settings(current)
            self._send(json.dumps(result), "application/json")
        except Exception as e:
            self._send(json.dumps({"ok": False, "error": str(e)}), "application/json", 400)

    def do_PATCH(self):
        if not authorize(self, globals().get("DATA_DIR", "/config"), "PATCH"):
            return
        path = self.path.split("?")[0]
        if path not in ("/settings", "/live-settings"):
            return self._send("not found", "text/plain", 404)
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        replace_maps = [key for key in query.get("replace", [""])[0].split(",") if key]
        return self._save_settings("/live-save" if path == "/live-settings" else "/save",
                                   partial=True, replace_maps=replace_maps)

    def do_PUT(self):
        if not authorize(self, globals().get("DATA_DIR", "/config"), "PUT"):
            return
        if attention_route(self, globals(), "PUT"):
            return
        if self.path.split("?")[0] != "/api/config":
            return self._send("not found", "text/plain", 404)
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 256 * 1024:
                raise ValueError("configuration body is invalid")
            incoming = json.loads(self.rfile.read(length))
            CONFIG_REPOSITORY.save(incoming)
            config = CONFIG_REPOSITORY.effective()
            if ATTENTION.get("value"):
                ATTENTION["value"].configure(config)
            ARBITER.minimum_relevance = config["context_engine"]["minimum_relevance"]
            ARBITER.takeovers_enabled = config["context_engine"]["takeovers_enabled"]
            ARBITER.post_event_plex_grace_seconds = (
                config["context_engine"]["post_event_plex_grace_minutes"] * 60)
            ARBITER.post_event_max_seconds = (
                config["context_engine"]["post_event_minutes"] * 60)
            ARBITER.rotation_seconds = config["fallback"]["rotation_seconds"]
            ARBITER.fallback_every = config["display"]["live_fallback_every"]
            ARBITER.minimum_context_seconds = config["display"]["minimum_context_seconds"]
            ARBITER.rotate_relevant = config["fallback"]["rotate_relevant"]
            ARBITER.single_item_seconds = config["fallback"]["single_item_seconds"]
            ARBITER.cast_ambient_interval_seconds = config["fallback"][
                "cast_ambient_interval_seconds"]
            ARBITER.cast_ambient_duration_seconds = config["fallback"][
                "cast_ambient_duration_seconds"]
            old = PROVIDER_ENGINE.get("value")
            PROVIDER_ENGINE["value"] = ContextEngine(
                create_providers(config, DATA_DIR), event_bus=EVENT_BUS)
            PROVIDER_ENGINE["value"].tick()
            if old:
                old.close()
            log_ok("configuration changed; provider registry reloaded")
            self._send(json.dumps({"ok": True, "config": CONFIG_REPOSITORY.public()}),
                       "application/json")
        except Exception as e:
            self._send(json.dumps({"ok": False, "error": str(e)}),
                       "application/json", 400)

    def do_DELETE(self):
        if not authorize(self, globals().get("DATA_DIR", "/config"), "DELETE"):
            return
        if self.path.split("?")[0] == "/api/screen-test":
            removed = delete_contexts()
            return self._send(json.dumps({"ok": True, "removed": removed}),
                              "application/json")
        if self.path.split("?")[0] != "/custom-backdrop":
            return self._send("not found", "text/plain", 404)
        try:
            os.unlink(CUSTOM_BACKDROP_PATH)
        except FileNotFoundError:
            pass
        except OSError as e:
            return self._send(json.dumps({"ok": False, "error": str(e)}),
                              "application/json", 500)
        self._send(json.dumps({"ok": True}), "application/json")



def handler_for(services):
    # Routes call application services by their established public names. The
    # composition root supplies those names once; handlers never import a
    # provider or upstream API directly. Mutable runtime state remains shared.
    globals().update({name: getattr(services, name) for name in dir(services)
                      if not name.startswith("__")})
    return WebHandler
