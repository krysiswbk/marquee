from datetime import timedelta

from .model import Context, EventState
from .provider import Provider


class AstronomyProvider(Provider):
    name = "astronomy"
    refresh_seconds = 900
    stale_seconds = 3600

    def fetch(self):
        return self.client.json("https://services.swpc.noaa.gov/json/planetary_k_index_1m.json")

    def contexts(self, payload, now):
        rows = payload if isinstance(payload, list) else []
        latest = rows[-1] if rows else {}
        kp = float(latest.get("estimated_kp") or latest.get("kp_index") or 0)
        threshold = float(self.config.get("kp_threshold", 6.0))
        self.reason = f"latest planetary Kp {kp:.1f}; threshold {threshold:.1f}"
        if kp < threshold:
            return []
        return [Context(
            id="astronomy:aurora", provider=self.name, type="astronomy", subtype="aurora",
            title="Aurora watch tonight", subtitle=f"Planetary Kp {kp:.1f}",
            body="Geomagnetic activity is elevated. Visibility this far south is possible, not guaranteed.",
            event_state=EventState.STARTING_SOON, priority=76, relevance=85, urgency=75,
            significance=95, freshness=95, expires_at=now + timedelta(hours=3),
            refresh_after=now + timedelta(minutes=15), icon="mdi:weather-night",
            accent="#5ee6a8", targets=["kiosk"],
            source_url="https://www.swpc.noaa.gov/products/aurora-viewline-tonight-and-tomorrow-night-experimental",
            stats=["Check for dark, clear northern skies", "NOAA SWPC geomagnetic observation"],
            raw={"kp": kp, "precisionNote": "Kp is planetary, not a local visibility forecast"})]
