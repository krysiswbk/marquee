"""Safe, short-lived contexts used by the admin screen test harness."""
from datetime import datetime, timedelta, timezone


# Self-contained screen-test art: fixtures must not create noisy browser 404s
# or make preview quality depend on a third-party athlete image remaining live.
FIGHTER_ONE_ART = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' "
                   "viewBox='0 0 320 320'%3E%3Crect width='320' height='320' "
                   "rx='160' fill='%23211b32'/%3E%3Ctext x='160' y='190' "
                   "text-anchor='middle' font-size='92' font-family='sans-serif' "
                   "font-weight='800' fill='white'%3EF1%3C/text%3E%3C/svg%3E")
FIGHTER_TWO_ART = FIGHTER_ONE_ART.replace("F1", "F2").replace("%23211b32", "%23162732")


SAMPLES = {
    "ufc_live": {
        "source": "ufc", "type": "ufc_live", "title": "UFC Fight Night",
        "subtitle": "Main Event · Welterweight", "status": "LIVE",
        "detail": "Round 3 · 2:14", "accent": "#d20a0a",
        "left": {"name": "Fighter One", "record": "18–3",
                  "logo": FIGHTER_ONE_ART},
        "right": {"name": "Fighter Two", "record": "16–2",
                  "logo": FIGHTER_TWO_ART},
        "rows": ["Last: Winner · TKO R2", "Up next: Co-main event"],
    },
    "pfl_live": {
        "source": "pfl", "type": "pfl_live", "title": "PFL Fight Night",
        "subtitle": "Main Event · Lightweight", "status": "LIVE",
        "detail": "Round 2 · 3:10", "accent": "#d4a62c",
        "left": {"name": "Fighter One", "record": "18–3", "logo": FIGHTER_ONE_ART},
        "right": {"name": "Fighter Two", "record": "16–2", "logo": FIGHTER_TWO_ART},
        "rows": ["Last: Winner · Decision", "Up next: Main event"],
    },
    "nhl_live": {
        "source": "nhl", "type": "nhl_live", "title": "Maple Leafs vs Canadiens",
        "subtitle": "Scotiabank Arena", "status": "2ND · 08:31",
        "detail": "Power play · TOR", "accent": "#147bcd",
        "left": {"name": "Toronto", "abbr": "TOR", "score": "3", "record": "42–24–6"},
        "right": {"name": "Montréal", "abbr": "MTL", "score": "2", "record": "35–30–7"},
        "rows": ["Shots 29–24", "Matthews · 2 goals"],
    },
    "weather": {
        "source": "weather", "type": "weather", "title": "Rain approaching",
        "subtitle": "Expected in 34 minutes", "status": "STARTING SOON",
        "detail": "A band of rain is moving toward home from the west.",
        "background": "/provider-assets/weather-radar.img",
        "rows": ["Rain 78%", "Wind 21 km/h", "Ending near 9:10 PM"],
    },
    "gaming": {
        "source": "gaming", "type": "gaming", "title": "Nintendo Direct",
        "subtitle": "Tomorrow · 10:00 AM (PS5/Xbox/Series X/Switch/Steam/PC)", "status": "UPCOMING",
        "detail": "A notable showcase matching your Nintendo interests.",
        "artwork": "https://upload.wikimedia.org/wikipedia/commons/0/0d/Nintendo.svg",
        "rows": ["40 minute presentation", "Watch live on YouTube", "Nintendo platform showcase"],
    },
    "tv": {
        "source": "tv", "type": "tv_release", "title": "New episode available",
        "subtitle": "Tracked household series", "status": "AVAILABLE NOW",
        "detail": "Season 2 · Episode 6", "rows": ["Added today", "52 minutes"],
    },
    "fallback": {
        "source": "fallback", "type": "fallback", "title": "Tonight at home",
        "subtitle": "Your ambient Marquee", "status": "NOW",
        "detail": "Weather, upcoming media and household highlights.",
        "rows": ["No urgent events", "Live data continues to refresh"],
    },
}


def sample_catalog():
    return [{"id": key, "provider": value["source"], "type": value["type"],
             "title": value["title"]} for key, value in SAMPLES.items()]


def forced_context(source, destination, duration_seconds=120, now=None):
    """Return a validated-context-compatible copy without mutating its source."""
    if destination not in ("live", "cast", "both"):
        raise ValueError("destination must be live, cast, or both")
    try:
        duration = int(duration_seconds)
    except (TypeError, ValueError):
        raise ValueError("durationSeconds must be a whole number")
    if not 10 <= duration <= 1800:
        raise ValueError("durationSeconds must be between 10 and 1800")
    now = now or datetime.now(timezone.utc)
    value = dict(source)
    value.update({
        "id": "screen-test:" + destination,
        "priority": 100,
        "targets": ({"live": ["kiosk"], "cast": ["hubs"],
                     "both": ["kiosk", "hubs"]}[destination]),
        "expires": (now + timedelta(seconds=duration)).isoformat(),
    })
    return value
