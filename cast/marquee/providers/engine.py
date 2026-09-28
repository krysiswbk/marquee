import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone


def provider_error_summary(error):
    """Return safe diagnostics copy while retaining the raw error for logs."""
    text = str(error).lower()
    if "returned non-zero exit status" in text or "subprocess" in text or "curl" in text:
        return "The provider request failed. Check the source connection or try again."
    if isinstance(error, TimeoutError) or "timed out" in text or "timeout" in text:
        return "The provider took too long to respond. Check the source connection or try again."
    if "http error" in text or "status code" in text:
        return "The provider returned an error response. Check the source settings or try again."
    return "The provider could not be reached. Check the source settings or try again."


class ContextEngine:
    def __init__(self, providers, clock=None, event_bus=None):
        self.providers = {p.name: p for p in providers}
        self.clock = clock or time.time
        self.event_bus = event_bus
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
                health.update(state="disabled", reason=provider.config.get(
                    "disabled_reason", "disabled by configuration"))
                continue
            future = self.futures.get(name)
            if future and future.done():
                started = health.get("startedAt", now_ts)
                health["lastFetch"] = datetime.fromtimestamp(now_ts, timezone.utc).isoformat()
                try:
                    payload, stale = future.result()
                    now = datetime.fromtimestamp(now_ts, timezone.utc)
                    found = provider.contexts(payload, now)
                    provider_weight = int(provider.config.get("priority", 0))
                    for context in found:
                        context.raw.setdefault("providerWeight", provider_weight)
                    threshold = float(provider.config.get("_minimum_relevance", 0))
                    with self.lock: self.candidates[name] = found
                    success_reason = getattr(provider, "reason", "fetched successfully")
                    health_details = provider.health_details(payload)
                    health.update(state="stale" if stale else "ok", stale=stale,
                                  lastSuccess=now.isoformat(), candidateContexts=len(found),
                                  eligibleContexts=sum(not c.expired(now) and
                                      c.event_state.value != "POST_EVENT" and
                                      provider_weight >= threshold and
                                      c.relevance >= threshold for c in found), error=None,
                                  errorSummary=None,
                                  cacheAgeSeconds=(round(provider.cache_age, 1)
                                                   if provider.cache_age is not None else None),
                                  durationMs=round((now_ts - started) * 1000, 1),
                                  reason=success_reason, lastSuccessReason=success_reason)
                    if health_details:
                        health.update(health_details)
                    if self.event_bus:
                        self.event_bus.publish("provider.updated", provider=name,
                                               candidates=len(found), stale=stale)
                except Exception as error:
                    summary = provider_error_summary(error)
                    health.update(state="error", error=summary, errorSummary=summary,
                                  reason="provider fetch failed")
                    if self.event_bus:
                        self.event_bus.publish("provider.error", provider=name,
                                               error=str(error))
                health["nextRefresh"] = datetime.fromtimestamp(
                    now_ts + provider.refresh_seconds, timezone.utc).isoformat()
                health["dueAt"] = now_ts + provider.refresh_seconds
                self.futures.pop(name, None)
            if name not in self.futures and now_ts >= health.get("dueAt", 0):
                health.update(state="fetching", lastFetch=datetime.fromtimestamp(
                    now_ts, timezone.utc).isoformat(), startedAt=now_ts)
                self.futures[name] = self.pool.submit(provider.cached_fetch)

    def all_contexts(self, now=None, display=None):
        now = now or datetime.fromtimestamp(self.clock(), timezone.utc)
        with self.lock:
            values = [c for contexts in self.candidates.values() for c in contexts]
        return [c for c in values if not c.expired(now)
                and c.event_state.value != "POST_EVENT"
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

    def refresh(self, name=None):
        """Make one or all providers due without waiting for their interval."""
        names = (name,) if name else tuple(self.providers)
        for provider_name in names:
            if provider_name in self.health:
                self.health[provider_name]["dueAt"] = 0
        self.tick()

    def close(self):
        self.pool.shutdown(wait=False, cancel_futures=True)
