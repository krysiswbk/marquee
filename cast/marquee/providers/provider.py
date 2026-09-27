import json
import os
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone


def atomic_json(path, value):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".provider-", dir=os.path.dirname(path))
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(value, handle)
        os.replace(tmp, path)
    finally:
        try: os.unlink(tmp)
        except OSError: pass


class HttpClient:
    def json(self, url, headers=None, timeout=8):
        request = urllib.request.Request(url, headers={
            "User-Agent": "MarqueeContext/1.0", "Accept": "application/json",
            **(headers or {})})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)

    def bytes(self, url, headers=None, timeout=10):
        request = urllib.request.Request(url, headers={"User-Agent": "MarqueeContext/1.0",
                                                       **(headers or {})})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read(), response.headers.get_content_type()


class Provider:
    name = "provider"
    refresh_seconds = 900
    stale_seconds = 3600

    def __init__(self, config, data_dir, client=None, clock=None):
        self.config, self.data_dir = config, data_dir
        self.client, self.clock = client or HttpClient(), clock or time.time
        self.cache_path = os.path.join(data_dir, "provider-cache", self.name + ".json")
        self.cache_age = None

    @property
    def enabled(self):
        return bool(self.config.get("enabled", False))

    def fetch(self):
        raise NotImplementedError

    def contexts(self, payload, now):
        raise NotImplementedError

    def cached_fetch(self):
        try:
            payload = self.fetch()
            self.cache_age = 0
            atomic_json(self.cache_path, {"at": self.clock(), "payload": payload})
            return payload, False
        except Exception:
            try:
                with open(self.cache_path) as handle: cached = json.load(handle)
                self.cache_age = self.clock() - float(cached["at"])
                if self.cache_age <= self.stale_seconds:
                    return cached["payload"], True
            except (OSError, ValueError, KeyError, TypeError):
                pass
            raise

    def health_template(self):
        return {"provider": self.name, "state": "disabled" if not self.enabled else "starting",
                "lastFetch": None, "lastSuccess": None, "nextRefresh": None,
                "lastSuccessReason": None,
                "candidateContexts": 0, "eligibleContexts": 0, "error": None,
                "stale": False, "cacheAgeSeconds": None, "durationMs": None,
                "reason": ""}
