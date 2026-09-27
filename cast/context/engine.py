import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone


class ContextEngine:
    def __init__(self, providers, clock=None):
        self.providers = {p.name: p for p in providers}
        self.clock = clock or time.time
        self.lock = threading.Lock()
        self.health = {p.name: p.health_template() for p in providers}
        self.candidates = {p.name: [] for p in providers}
        self.futures = {}
        self.pool = ThreadPoolExecutor(max_workers=min(4, max(1, len(providers))),
                                       thread_name_prefix="marquee-provider")

    def tick(self):
        now_ts = self.clock()
        for name, provider in self.providers.items():
            health = self.health[name]
            if not provider.enabled:
                health.update(state="disabled", reason="disabled by configuration")
                continue
            future = self.futures.get(name)
            if future and future.done():
                health["lastFetch"] = datetime.fromtimestamp(now_ts, timezone.utc).isoformat()
                try:
                    payload, stale = future.result()
                    now = datetime.fromtimestamp(now_ts, timezone.utc)
                    found = provider.contexts(payload, now)
                    with self.lock: self.candidates[name] = found
                    health.update(state="stale" if stale else "ok", stale=stale,
                                  lastSuccess=now.isoformat(), candidateContexts=len(found),
                                  eligibleContexts=sum(not c.expired(now) for c in found), error=None,
                                  reason=getattr(provider, "reason", "fetched successfully"))
                except Exception as error:
                    health.update(state="error", error=str(error), reason="provider fetch failed")
                health["nextRefresh"] = datetime.fromtimestamp(
                    now_ts + provider.refresh_seconds, timezone.utc).isoformat()
                health["dueAt"] = now_ts + provider.refresh_seconds
                self.futures.pop(name, None)
            if name not in self.futures and now_ts >= health.get("dueAt", 0):
                health.update(state="fetching", lastFetch=datetime.fromtimestamp(
                    now_ts, timezone.utc).isoformat())
                self.futures[name] = self.pool.submit(provider.cached_fetch)

    def all_contexts(self, now=None, display=None):
        now = now or datetime.fromtimestamp(self.clock(), timezone.utc)
        with self.lock:
            values = [c for contexts in self.candidates.values() for c in contexts]
        return [c for c in values if not c.expired(now)
                and (not display or display in c.targets)]

    def winner(self, now=None, display=None):
        values = self.all_contexts(now, display)
        return max(values, key=lambda c: (c.score(), c.start_time or now), default=None)

    def diagnostics(self):
        self.tick()
        with self.lock:
            result = {name: {**self.health[name],
                             "contexts": [c.to_dict() for c in self.candidates[name]]}
                      for name in self.providers}
        return {"providers": result,
                "active": {d: (self.winner(display=d).to_dict()
                                if self.winner(display=d) else None)
                           for d in ("kiosk", "hubs")}}
