from pathlib import Path
import yaml

path = Path("/config/apps/apps.yaml")
config = yaml.safe_load(path.read_text()) or {}
config["marquee_sources"] = {
    "module": "marquee_sources", "class": "MarqueeSources",
    "marquee_url": "http://10.10.9.37:8084",
    "radar_entity": "camera.halton_hills_radar",
    "sensor_prefix": "sensor.environment_canada_",
    "kiosk_browser": "a38e5c41-b99f0451",
    "game_release_calendar_terms": ["game release", "game releases", "video game"],
    "game_release_lookahead_days": 30,
}
path.write_text(yaml.safe_dump(config, sort_keys=False))
print("marquee_sources configured")
