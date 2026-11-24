#!/usr/bin/env python3
"""Keep the HA kiosk launch automation aligned with its top-level wrapper.

Dry-run reads the automation without writing. Apply saves a private rollback
copy, checks the installed wrapper, updates the launch action, and reloads HA
automations.
"""

import argparse
import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from kiosk_wrapper import WRAPPER_PATH, WRAPPER_SOURCE, redirect_popup_data

AUTOMATION_ID = "kiosk_marquee_plex_overlay"


def plan(current):
    updated = copy.deepcopy(current)
    triggers = updated.get("triggers")
    if not isinstance(triggers, list) or not all(isinstance(trigger, dict) for trigger in triggers):
        raise ValueError("Kiosk automation triggers changed")
    updated["triggers"] = [trigger for trigger in triggers if trigger.get("id") != "kiosk_idle"]
    try:
        sequence = updated["actions"][0]["choose"][0]["sequence"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("Kiosk automation layout changed") from error
    if len(sequence) == 3:
        if sequence[0].get("action") != "browser_mod.refresh" or sequence[1].get("delay") != "00:00:08":
            raise ValueError("Unexpected kiosk launch sequence")
    elif len(sequence) != 1:
        raise ValueError("Unexpected kiosk launch sequence")
    popup = sequence[-1]
    if popup.get("action") != "browser_mod.popup" or popup.get("data", {}).get("tag") != "marquee":
        raise ValueError("Expected tagged Marquee popup")
    updated["actions"][0]["choose"][0]["sequence"] = [
        {"action": "browser_mod.popup", "data": redirect_popup_data()}
    ]
    guard = {
        "condition": "not",
        "conditions": [{
            "condition": "state",
            "entity_id": "sensor.sb2_kiosk_browser_path",
            "state": "/browser-mod",
        }],
    }
    conditions = updated["actions"][0]["choose"][0]["conditions"]
    if guard not in conditions:
        conditions.append(guard)
    return updated


def request(base_url, token, method, path, payload=None):
    body = None if payload is None else json.dumps(payload).encode()
    headers = {"Authorization": f"Bearer {token}"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    req = Request(base_url.rstrip("/") + path, body, headers, method=method)
    with urlopen(req, timeout=20) as response:
        data = response.read()
    return json.loads(data) if data else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dry-run", "apply"))
    parser.add_argument("--base-url", default="http://10.10.9.5:8123")
    parser.add_argument("--backup-dir", type=Path)
    args = parser.parse_args()
    token = os.environ.get("HA_TOKEN")
    if not token:
        parser.error("HA_TOKEN is required")
    if args.mode == "apply" and args.backup_dir is None:
        parser.error("--backup-dir is required for apply")
    path = f"/api/config/automation/config/{AUTOMATION_ID}"
    current = request(args.base_url, token, "GET", path)
    updated = plan(current)
    if updated == current:
        print("Kiosk popup already matches Marquee source")
        return
    if args.mode == "dry-run":
        print("Kiosk popup differs from Marquee source")
        return
    wrapper_url = args.base_url.rstrip("/") + WRAPPER_PATH
    with urlopen(wrapper_url, timeout=20) as response:
        if response.read() != WRAPPER_SOURCE.read_bytes():
            raise RuntimeError("Installed kiosk wrapper does not match source; no automation write made")
    if request(args.base_url, token, "GET", path) != current:
        raise RuntimeError("Automation changed during review; no write made")
    args.backup_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    backup = args.backup_dir / (AUTOMATION_ID + "-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + ".json")
    with backup.open("x") as file:
        os.chmod(backup, 0o600)
        json.dump(current, file, indent=2)
        file.write("\n")
    request(args.base_url, token, "POST", path, updated)
    if request(args.base_url, token, "GET", path) != updated:
        raise RuntimeError(f"Automation readback mismatch; rollback copy: {backup}")
    request(args.base_url, token, "POST", "/api/services/automation/reload", {})
    print(f"Kiosk popup synchronized; rollback copy: {backup}")


if __name__ == "__main__":
    main()
