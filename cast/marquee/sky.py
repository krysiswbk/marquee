"""Validation helpers for the optional real-data ambient sky contract."""
import math


def finite(value, low=None, high=None):
    if value is None or isinstance(value, bool):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(value) or (low is not None and value < low) or (high is not None and value > high):
        return None
    return value


def clean_sky(value):
    """Return a bounded sky object, or omit it when no usable data exists."""
    if not isinstance(value, dict):
        return None
    result = {}
    condition = str(value.get("condition", "")).strip()[:40]
    if condition:
        result["condition"] = condition
    cloud = finite(value.get("cloud_cover"), 0, 100)
    if cloud is not None:
        result["cloud_cover"] = cloud
    visibility = finite(value.get("visibility"), 0, 100000)
    if visibility is not None:
        result["visibility"] = visibility
        # The live HA bridge's visibility source is its normalized
        # sensor.open_meteo_visibility sensor, whose configured unit is km.
        # Older bridge payloads omit the unit; keep those readings truthful.
        unit = str(value.get("visibility_unit", "km")).strip()[:12]
        result["visibility_unit"] = unit or "km"
    sun = value.get("sun")
    if isinstance(sun, dict):
        clean = {}
        for key, bounds in (("elevation", (-90, 90)), ("azimuth", (0, 360))):
            number = finite(sun.get(key), *bounds)
            if number is not None:
                clean[key] = number
        if isinstance(sun.get("is_day"), bool):
            clean["is_day"] = sun["is_day"]
        if clean:
            result["sun"] = clean
    moon = value.get("moon")
    if isinstance(moon, dict):
        clean = {}
        phase = str(moon.get("phase", "")).strip()[:32]
        if phase:
            clean["phase"] = phase
        for key, bounds in (("illumination", (0, 1)), ("elevation", (-90, 90)), ("azimuth", (0, 360))):
            number = finite(moon.get(key), *bounds)
            if number is not None:
                clean[key] = number
        if clean:
            result["moon"] = clean
    aircraft = value.get("aircraft")
    if isinstance(aircraft, list):
        tracks = []
        for item in aircraft[:12]:
            if not isinstance(item, dict) or not str(item.get("id", "")).strip():
                continue
            track = {"id": str(item["id"]).strip()[:64]}
            callsign = str(item.get("callsign") or "").strip()
            if callsign:
                track["callsign"] = callsign[:32]
            for key, bounds in (("bearing", (0, 360)), ("elevation", (-90, 90)), ("altitude", (-2000, 30000)), ("speed", (0, 2000)), ("heading", (0, 360))):
                number = finite(item.get(key), *bounds)
                if number is not None:
                    track[key] = number
            if "bearing" in track and "elevation" in track:
                tracks.append(track)
        if tracks:
            result["aircraft"] = tracks
    return result or None
