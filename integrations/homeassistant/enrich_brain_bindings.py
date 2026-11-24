"""Reconcile observed room and laundry sensors into the Marquee house briefing.

The attention bridge discovers its HA allowlist from Marquee, so these context
bindings make the existing sensors available without forwarding HA credentials.
"""

import argparse
import json
from urllib.request import Request, urlopen

BINDINGS = {
    "living_room_occupied": "binary_sensor.living_room_occupancy",
    "bedroom_occupied": "binary_sensor.bedroom_occupancy",
    "nursery_motion": "binary_sensor.nursery_motion_sensor_motion",
    "laundry_vibration": "binary_sensor.laundry_vibration_sensor_vibration",
}


def reconciled(config):
    result = dict(config)
    contexts = dict(result["context_bindings"])
    for name, entity in BINDINGS.items():
        contexts[name] = {"entity_id": entity, "values": {"on": True, "off": False}}
    result["context_bindings"] = contexts
    return result


def read_json(url):
    with urlopen(url, timeout=10) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8084")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    base = args.url.rstrip("/")
    current = read_json(base + "/api/attention")["config"]
    desired = reconciled(current)
    changed = current != desired
    if args.apply and changed:
        request = Request(base + "/api/attention/config", data=json.dumps(desired).encode(),
                          headers={"Content-Type": "application/json"}, method="PUT")
        with urlopen(request, timeout=10) as response:
            if not json.load(response).get("ok"):
                raise RuntimeError("Marquee rejected attention configuration")
        manifest = read_json(base + "/api/attention/bindings")
        if not set(BINDINGS.values()).issubset(manifest["entities"]):
            raise RuntimeError("Room and laundry sensors missing from HA bridge allowlist")
    print(json.dumps({"changed": changed, "applied": args.apply and changed,
                      "entities": list(BINDINGS.values())}))


if __name__ == "__main__":
    main()
