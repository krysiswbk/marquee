"""Canonical context deduplication, enrichment and display arbitration."""
import re
import threading
from datetime import datetime, timedelta, timezone


PLACEHOLDER = re.compile(r"^(?:tba|tbd|unknown|untitled|to be (?:announced|determined))$", re.I)


def placeholder_context(item):
    """Reject placeholder release metadata before it can score or rotate."""
    title = str(item.get("title", "")).strip().strip("[]()")
    subtitle = str(item.get("subtitle", "")).strip()
    # Sonarr renders "S02E03 · Episode title". Inspect the episode-title
    # portion independently so a real series title cannot mask a TBA episode.
    episode_title = subtitle.rsplit("·", 1)[-1].strip().strip("[]()")
    return (bool(title and PLACEHOLDER.fullmatch(title)) or
            (str(item.get("type", "")).lower() == "tv_release" and
             "·" in subtitle and bool(PLACEHOLDER.fullmatch(episode_title))))


class ContextArbiter:
    def __init__(self, event_bus=None, minimum_relevance=0, takeovers_enabled=True,
                 post_event_plex_grace_seconds=0, post_event_max_seconds=1800,
                 rotation_seconds=30, fallback_every=2,
                 rotate_relevant=True, single_item_seconds=12,
                 minimum_context_seconds=12):
        self.event_bus = event_bus
        self.minimum_relevance = minimum_relevance
        self.takeovers_enabled = takeovers_enabled
        self.post_event_plex_grace_seconds = post_event_plex_grace_seconds
        self.post_event_max_seconds = post_event_max_seconds
        self.rotation_seconds = max(5, int(rotation_seconds))
        self.fallback_every = max(0, int(fallback_every))
        self.rotate_relevant = bool(rotate_relevant)
        self.single_item_seconds = max(5, int(single_item_seconds))
        self.minimum_context_seconds = max(0, int(minimum_context_seconds))
        self._selected = {}
        self._selected_at = {}
        self._first_seen = {}
        self._lock = threading.RLock()
        self._available = {}
        self._manual = {}

    def control_state(self, display="kiosk"):
        with self._lock:
            ids = self._available.get(display, [])
            selected = self._selected.get(display)
            manual = self._manual.get(display, {})
            return {"frozen": manual.get("frozen", False),
                    "selected": selected, "count": len(ids),
                    "position": ids.index(selected) + 1 if selected in ids else 0}

    def control(self, action, display="kiosk", now=None):
        if display != "kiosk" or action not in ("next", "previous", "freeze", "resume"):
            raise ValueError("invalid display control")
        now = now or datetime.now(timezone.utc)
        with self._lock:
            ids = self._available.get(display, [])
            selected = self._selected.get(display)
            old = self._manual.get(display, {})
            if action == "resume":
                self._manual.pop(display, None)
                self._selected_at[display] = now - timedelta(seconds=self.minimum_context_seconds)
            elif selected in ids:
                if action in ("next", "previous"):
                    selected = ids[(ids.index(selected) + (1 if action == "next" else -1)) % len(ids)]
                self._manual[display] = {
                    "id": selected, "frozen": action == "freeze" or old.get("frozen", False),
                    "until": now.timestamp() + self.rotation_seconds}
            return self.control_state(display)

    @staticmethod
    def _expired(candidate, now):
        value = candidate.get("expires") or candidate.get("expires_at")
        if not value:
            return False
        try:
            expires = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if not expires.tzinfo:
                expires = expires.replace(tzinfo=timezone.utc)
            return expires <= now
        except (TypeError, ValueError):
            return True

    @staticmethod
    def enrich(explicit, generated):
        """Fill missing generated fields without replacing household artwork."""
        for candidate in explicit:
            matches = [item for item in generated
                       if item.get("source") == candidate.get("source") and
                       item.get("title") == candidate.get("title")]
            if not matches:
                continue
            source = matches[0]
            for field in ("rows", "status", "detail", "background", "artwork"):
                if not candidate.get(field) and source.get(field):
                    candidate[field] = source[field]
        return explicit

    def select(self, explicit, generated, plex=None, display=None, now=None):
        with self._lock:
            return self._select(explicit, generated, plex, display, now)

    def _select(self, explicit, generated, plex=None, display=None, now=None):
        now = now or datetime.now(timezone.utc)
        if plex and not self.takeovers_enabled and display != "kiosk":
            return {"id": "plex:now", "priority": 70, "payload": plex}
        explicit = self.enrich([dict(item) for item in explicit], generated)
        # Household publishers often describe the same event as a built-in
        # provider. Keep the richer household candidate authoritative instead
        # of allowing the duplicate (flags, different expiry) to reappear when
        # the explicit result ages out.
        identities = {(item.get("source"), item.get("title")) for item in explicit}
        generated = [item for item in generated
                     if (item.get("source"), item.get("title")) not in identities]
        values = explicit + generated
        eligible = []
        for order, item in enumerate(values):
            if placeholder_context(item):
                continue
            seen_key = (item.get("id"), item.get("type"))
            observed = item.get("observedAt")
            try:
                first_seen = (datetime.fromisoformat(str(observed).replace("Z", "+00:00"))
                              if observed else self._first_seen.setdefault(seen_key, now))
                if not first_seen.tzinfo:
                    first_seen = first_seen.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                first_seen = self._first_seen.setdefault(seen_key, now)
            self._first_seen[seen_key] = first_seen
            if display and display not in item.get("targets", ("kiosk", "hubs")):
                continue
            if (str(item.get("eventState", "")).upper() == "POST_EVENT" or
                    str(item.get("event_state", "")).upper() == "POST_EVENT" or
                    str(item.get("type", "")).lower().endswith("_post")):
                continue
            if self._expired(item, now):
                continue
            # Provider weight is a hard eligibility decision, not merely a
            # sort hint. Generated contexts carry it explicitly; external
            # legacy contexts fall back to their priority.
            if float(item.get("providerWeight", item.get("priority", 0))) < self.minimum_relevance:
                continue
            if float(item.get("relevance", 100)) < self.minimum_relevance:
                continue
            if (str(item.get("type", "")).endswith("_post") and
                    (now - first_seen).total_seconds() >=
                    self.post_event_max_seconds):
                continue
            eligible.append((item, order))
        if plex:
            # Results get a brief victory/recap takeover, then active household
            # viewing wins. Upcoming/live sports are unaffected.
            cutoff = now.timestamp() - self.post_event_plex_grace_seconds
            eligible = [(item, order) for item, order in eligible
                        if not (str(item.get("type", "")).endswith("_post") and
                                self._first_seen.get((item.get("id"), item.get("type")), now).timestamp() <= cutoff)]

        # UFC owns overlapping MMA coverage. Keep PFL out of automatic and
        # manual rotation while UFC is live or approaching; once UFC ends or
        # expires, PFL becomes eligible again. Apply this after expiry/target/
        # relevance filtering so stale or irrelevant UFC cannot block PFL.
        def league(item):
            return str(item.get("source") or str(item.get("type", "")).split("_")[0]).lower()

        def active_mma(item):
            state = str(item.get("eventState") or item.get("event_state", "")).upper()
            phase = str(item.get("type", "")).rsplit("_", 1)[-1].lower()
            if state in ("LIVE", "STARTING_SOON") or phase in ("in", "live"):
                return True
            if phase != "pre":
                return False
            try:
                starts = datetime.fromisoformat(str(item.get("starts", "")).replace("Z", "+00:00"))
                if not starts.tzinfo:
                    starts = starts.replace(tzinfo=timezone.utc)
                return -timedelta(hours=9) <= starts - now <= timedelta(hours=2)
            except (ValueError, TypeError):
                return False

        if any(league(item) == "ufc" and active_mma(item) for item, _ in eligible):
            eligible = [(item, order) for item, order in eligible if league(item) != "pfl"]

        # Cast receivers are intentionally calm. Playback belongs there; an
        # ambient release, deal, forecast or routine final score does not.
        # Providers can opt into a brief Cast interruption explicitly, while
        # priority 95+ remains the emergency/immediate-takeover tier.
        if display == "hubs":
            eligible = [(item, order) for item, order in eligible
                        if item.get("castTakeover") is True or
                        int(item.get("priority", 0)) >= 95]
        if plex:
            eligible.append(({"id": "plex:now", "priority": 70,
                              "payload": plex}, len(values)))

        if plex and not self.takeovers_enabled:
            eligible = [(item, order) for item, order in eligible if item.get("id") == "plex:now"]
        self._available[display] = [item["id"] for item, _ in sorted(
            eligible, key=lambda pair: (-int(pair[0].get("priority", 0)), str(pair[0].get("id", ""))))]
        manual = self._manual.get(display)
        manual_winner = None
        if manual:
            manual_winner = next((item for item, _ in eligible if item.get("id") == manual["id"]), None)
            if manual_winner is None or (not manual["frozen"] and now.timestamp() >= manual["until"]):
                self._manual.pop(display, None)
                manual_winner = None

        if display == "kiosk" and eligible:
            # Approaching and in-flight events should be stable, information-
            # rich experiences. Everything else is useful ambient data: rotate
            # it rather than letting the highest-scoring release occupy the
            # display all evening. The configured fallback is not a candidate;
            # it is rendered by the kiosk only when this method has no useful
            # eligible data at all.
            pinned = [(item, order) for item, order in eligible
                      if str(item.get("id", "")).startswith("screen-test:") or
                      (str(item.get("eventState", "")).upper() in
                       ("LIVE", "STARTING_SOON") and
                       int(item.get("priority", 0)) >= 80)]
            if pinned:
                winner = max(pinned, key=lambda pair:
                             (int(pair[0].get("priority", 0)), 1 if str(pair[0].get("source", "")).lower() == "ufc" else 0, -pair[1]))[0]
            else:
                ambient = sorted(eligible, key=lambda pair:
                                 (-int(pair[0].get("priority", 0)),
                                  str(pair[0].get("id", "")), pair[1]))
                if not self.rotate_relevant:
                    winner = ambient[0][0]
                    ambient = []
                if len(ambient) == 1:
                    # One worthwhile item remains worthwhile. In particular,
                    # active Plex playback must never blink to a clock merely
                    # because there is nothing else to rotate with.
                    winner = ambient[0][0]
                    ambient = []
                slot = int(now.timestamp() // self.rotation_seconds)
                if ambient:
                    winner = ambient[slot % len(ambient)][0]
        else:
            winner = max(eligible,
                         key=lambda pair: (int(pair[0].get("priority", 0)), -pair[1]),
                         default=(None, 0))[0]
        if manual_winner is not None:
            winner = manual_winner
        selected_id = winner.get("id") if winner else None
        previous = self._selected.get(display)
        selected_at = self._selected_at.get(display, now)
        if (manual_winner is None and previous and selected_id != previous and
                (now - selected_at).total_seconds() < self.minimum_context_seconds):
            prior = next((item for item, _ in eligible if item.get("id") == previous), None)
            if prior is not None:
                winner, selected_id = prior, previous
        if self._selected.get(display) != selected_id:
            previous = self._selected.get(display)
            self._selected[display] = selected_id
            self._selected_at[display] = now
            if self.event_bus:
                self.event_bus.publish("context.selected", display=display,
                                       previous=previous, selected=selected_id)
        return winner
