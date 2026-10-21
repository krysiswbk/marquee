#!/usr/bin/env python3
"""Reversible HA dashboard control for reopening the existing Marquee popup.

Run inside the active HA AppDaemon add-on, which has SUPERVISOR_TOKEN and
mounts the HA config at /homeassistant.
No command writes until ``apply``. ``dry-run --config-json`` also works offline.
"""

import argparse
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone


DASHBOARD = "dashboard-homepage"
STORAGE = Path("/homeassistant/.storage/lovelace.dashboard_homepage")
BACKUP_ROOT = Path("/homeassistant/marquee-dashboard-rollback")
BROWSER_ID = "a38e5c41-b99f0451"
MARQUEE_URL = "http://10.10.9.37:8084/kiosk?v=household-desk-2.12.80"
POPUP_STYLE = 'ha-dialog{--ha-dialog-surface-background:#000;--ha-dialog-border-radius:0!important;--dialog-content-padding:0;--padding-x:0;--padding-y:0}.container,.content,.content .container{margin:0!important;padding:0!important}.header,ha-dialog-header{position:absolute!important;top:10px;right:10px;z-index:30;width:44px!important;min-height:44px!important;padding:0!important;border-radius:50%;background:rgba(0,0,0,.55)!important}.title{display:none!important}'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def card():
    return {
        "type": "custom:mushroom-template-card",
        "primary": "Show Marquee",
        "secondary": "Return to the household display",
        "icon": "mdi:monitor-dashboard",
        "icon_color": "purple",
        "layout": "horizontal",
        "tap_action": {
            "action": "perform-action",
            "perform_action": "browser_mod.popup",
            "data": {
                "browser_id": [BROWSER_ID],
                "title": "Marquee",
                "dismissable": True,
                "tag": "marquee",
                "initial_style": "marquee-fullscreen",
                "style_sequence": ["marquee-fullscreen"],
                "popup_styles": [{
                    "style": "marquee-fullscreen",
                    "include_styles": ["fullscreen"],
                    "styles": POPUP_STYLE,
                }],
                "content": {
                    "type": "iframe",
                    "url": MARQUEE_URL,
                    "aspect_ratio": "57.27%",
                    "card_mod": {"style": "ha-card { border:0; box-shadow:none; }"},
                },
            },
        },
        "card_mod": {"style": "ha-card { background: transparent !important; box-shadow: none; border: none; }"},
    }


def locate_stacks(config):
    views = config.get("views")
    if not isinstance(views, list) or len(views) < 5:
        raise ValueError("Dashboard view structure changed; no edit made")
    targets = ((0, "Devices"), (4, "Cameras"))
    for index, label in targets:
        view = views[index]
        if not isinstance(view, dict) or not isinstance(view.get("cards"), list):
            raise ValueError(f"{label} view {index} has no cards list")
        if label == "Cameras" and view.get("path") != "cameras":
            raise ValueError("Cameras is no longer view 4/path cameras")
        if label == "Devices" and view.get("path") not in (None, "", "0", "devices"):
            raise ValueError("Devices is no longer the default view 0")
        if label == "Devices" and view.get("type") != "custom:horizontal-layout":
            raise ValueError("Devices view layout changed")
        if label == "Cameras" and view.get("type") != "masonry":
            raise ValueError("Cameras view layout changed")
        if not view["cards"] or not isinstance(view["cards"][0], dict):
            raise ValueError(f"{label} first stack missing")
        stack = view["cards"][0]
        if stack.get("type") != "custom:vertical-stack-in-card":
            raise ValueError(f"{label} first card is no longer the expected stack")
        children = stack.get("cards")
        if not isinstance(children, list) or len(children) < 1:
            raise ValueError(f"{label} first stack has no child cards")
        first_expected = "horizontal-stack" if label == "Devices" else "custom:mushroom-title-card"
        if not isinstance(children[0], dict) or children[0].get("type") != first_expected:
            raise ValueError(f"{label} first stack's header changed")
        yield label, children


def plan(config):
    revised = copy.deepcopy(config)
    changes = []
    expected = card()
    for label, children in locate_stacks(revised):
        matches = [i for i, child in enumerate(children)
                   if isinstance(child, dict) and child.get("type") == "custom:mushroom-template-card"
                   and child.get("primary") == "Show Marquee"]
        if len(matches) > 1:
            raise ValueError(f"Duplicate Marquee controls on {label}; no edit made")
        if matches:
            if children[matches[0]] != expected:
                raise ValueError(f"Existing Marquee control differs on {label}; no edit made")
            changes.append({"view": label, "action": "already present", "index": matches[0]})
        else:
            children.insert(1, copy.deepcopy(expected))
            changes.append({"view": label, "action": "insert", "index": 1})
    return revised, changes


async def command(ws, ident, kind, **kwargs):
    await ws.send_json({"id": ident, "type": kind, **kwargs})
    while True:
        response = await ws.receive_json()
        if response.get("id") == ident:
            if not response.get("success"):
                raise RuntimeError(f"HA {kind} failed: {response.get('error')}")
            return response.get("result")


async def with_config(args):
    import aiohttp

    token = os.environ.get("SUPERVISOR_TOKEN") or os.environ.get("HASSIO_TOKEN")
    if not token:
        raise RuntimeError("Run in the active HA AppDaemon add-on with Supervisor token")
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect("http://supervisor/core/websocket") as ws:
            greeting = await ws.receive_json()
            if greeting.get("type") != "auth_required":
                raise RuntimeError("Unexpected HA websocket greeting")
            await ws.send_json({"type": "auth", "access_token": token})
            if (await ws.receive_json()).get("type") != "auth_ok":
                raise RuntimeError("HA websocket authentication failed")
            current = await command(ws, 1, "lovelace/config", url_path=DASHBOARD)
            if args.mode == "rollback":
                manifest_path = Path(args.manifest)
                manifest = json.loads(manifest_path.read_text())
                if manifest.get("dashboard") != DASHBOARD:
                    raise RuntimeError("Rollback manifest names a different dashboard")
                backup_storage = manifest_path.parent / "storage-before.json"
                if hashlib.sha256(backup_storage.read_bytes()).hexdigest() != manifest["storage_sha256"]:
                    raise RuntimeError("Storage backup hash mismatch")
                original = json.loads((manifest_path.parent / "config-before.json").read_text())
                if digest(original) != manifest["config_before_sha256"]:
                    raise RuntimeError("Config backup hash mismatch")
                if digest(current) != manifest["config_after_sha256"]:
                    raise RuntimeError("Dashboard changed since apply; refusing to overwrite newer edits")
                await command(ws, 2, "lovelace/config/save", url_path=DASHBOARD, config=original)
                verified = await command(ws, 3, "lovelace/config", url_path=DASHBOARD)
                if verified != original:
                    raise RuntimeError("Rollback save did not round-trip")
                print(json.dumps({"status": "rolled back", "config_sha256": digest(verified)}))
                return
            revised, changes = plan(current)
            if args.mode == "dry-run":
                print(json.dumps({"status": "dry-run", "changes": changes,
                                  "before_sha256": digest(current), "after_sha256": digest(revised)}))
                return
            if revised == current:
                print(json.dumps({"status": "already applied", "changes": changes}))
                return
            if not STORAGE.is_file():
                raise RuntimeError("HA storage file unavailable; refusing save without raw backup")
            raw_storage = STORAGE.read_bytes()
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_dir = BACKUP_ROOT / f"show-marquee-{stamp}-{digest(current)[:12]}"
            backup_dir.mkdir(mode=0o700, parents=True, exist_ok=False)
            for name, payload in (("storage-before.json", raw_storage),
                                  ("config-before.json", canonical(current))):
                path = backup_dir / name
                with path.open("xb") as output:
                    os.chmod(path, 0o600)
                    output.write(payload)
                    output.flush()
                    os.fsync(output.fileno())
            manifest = {"dashboard": DASHBOARD, "storage_sha256": hashlib.sha256(raw_storage).hexdigest(),
                        "config_before_sha256": digest(current), "config_after_sha256": digest(revised),
                        "changes": changes}
            manifest_path = backup_dir / "manifest.json"
            with manifest_path.open("x") as output:
                os.chmod(manifest_path, 0o600)
                json.dump(manifest, output, sort_keys=True, indent=2)
                output.flush()
                os.fsync(output.fileno())
            # Re-read before save to avoid racing another HA dashboard editor.
            latest = await command(ws, 2, "lovelace/config", url_path=DASHBOARD)
            if latest != current:
                raise RuntimeError("Dashboard changed after backup; refusing save")
            await command(ws, 3, "lovelace/config/save", url_path=DASHBOARD, config=revised)
            verified = await command(ws, 4, "lovelace/config", url_path=DASHBOARD)
            if verified != revised:
                raise RuntimeError(f"Save did not round-trip; rollback manifest: {manifest_path}")
            print(json.dumps({"status": "applied", "changes": changes, "manifest": str(manifest_path),
                              "after_sha256": digest(verified)}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("dry-run", "apply", "rollback"))
    parser.add_argument("--config-json", type=Path, help="offline dry-run fixture only")
    parser.add_argument("--manifest", help="manifest created by apply, required for rollback")
    args = parser.parse_args()
    if args.config_json:
        if args.mode != "dry-run":
            parser.error("--config-json is only accepted with dry-run")
        before = json.loads(args.config_json.read_text())
        after, changes = plan(before)
        print(json.dumps({"status": "offline dry-run", "changes": changes,
                          "before_sha256": digest(before), "after_sha256": digest(after)}))
        return
    if args.mode == "rollback" and not args.manifest:
        parser.error("rollback requires --manifest")
    asyncio.run(with_config(args))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
