#!/usr/bin/env python3
"""Constrained MQTT-to-backlight bridge for the kitchen HA kiosk."""

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

CONFIG = Path("/home/wbk/.config/lnxlink/config.yaml")
COMMAND_TOPIC = "homelab/kiosk/display/brightness/set"
STATE_TOPIC = "homelab/kiosk/display/brightness/state"
BACKLIGHT_POWER = Path("/sys/class/backlight/intel_backlight/bl_power")
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
LOG = logging.getLogger("kiosk-display-agent")


def set_ambient(enabled: bool) -> None:
    subprocess.run(
        [
            "/usr/bin/gsettings",
            "set",
            "org.gnome.settings-daemon.plugins.power",
            "ambient-enabled",
            "true" if enabled else "false",
        ],
        check=True,
        timeout=10,
    )


def set_panel_power(enabled: bool) -> None:
    """Turn the LCD backlight fully off, beyond GNOME's minimum brightness."""
    BACKLIGHT_POWER.write_text("0" if enabled else "4")


def set_brightness(payload: bytes) -> str:
    requested = payload.decode("ascii").strip().lower()
    if requested == "auto":
        # Seed a usable level when waking from 0; GNOME then takes over as the
        # ambient sensor reports changes.
        set_ambient(False)
        set_panel_power(True)
        subprocess.run(
            [
                "/usr/bin/gdbus",
                "call",
                "--session",
                "--dest",
                "org.gnome.SettingsDaemon.Power",
                "--object-path",
                "/org/gnome/SettingsDaemon/Power",
                "--method",
                "org.freedesktop.DBus.Properties.Set",
                "org.gnome.SettingsDaemon.Power.Screen",
                "Brightness",
                "<50>",
            ],
            check=True,
            timeout=10,
        )
        set_ambient(True)
        return "auto"

    value = int(requested)
    if not 0 <= value <= 100:
        raise ValueError("brightness must be between 0 and 100")
    # Auto-brightness must not raise a deliberately blacked-out display.
    set_ambient(False)
    if value:
        set_panel_power(True)
    # GNOME owns the Surface backlight and immediately overwrites direct sysfs
    # writes. Set its Screen.Brightness property so the value remains stable.
    subprocess.run(
        [
            "/usr/bin/gdbus",
            "call",
            "--session",
            "--dest",
            "org.gnome.SettingsDaemon.Power",
            "--object-path",
            "/org/gnome/SettingsDaemon/Power",
            "--method",
            "org.freedesktop.DBus.Properties.Set",
            "org.gnome.SettingsDaemon.Power.Screen",
            "Brightness",
            f"<{value}>",
        ],
        check=True,
        timeout=10,
    )
    if value == 0:
        set_panel_power(False)
    return str(value)


def on_connect(client: Any, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
    if reason_code.is_failure:
        raise RuntimeError(f"MQTT connection failed: {reason_code}")
    result, message_id = client.subscribe(COMMAND_TOPIC, qos=1)
    LOG.info("connected; subscribed to %s (result=%s mid=%s)", COMMAND_TOPIC, result, message_id)


def on_message(client: Any, userdata: Any, message: Any) -> None:
    try:
        value = set_brightness(message.payload)
        LOG.info("applied display brightness mode %s", value)
        client.publish(STATE_TOPIC, value, qos=1, retain=True)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        LOG.error("rejected brightness command: %s", exc)
        client.publish(
            STATE_TOPIC,
            json.dumps({"error": str(exc)}),
            qos=1,
            retain=False,
        )


def main() -> None:
    import paho.mqtt.client as mqtt  # type: ignore[import-untyped,import-not-found]
    import yaml  # type: ignore[import-untyped]

    config = yaml.safe_load(CONFIG.read_text())
    broker = config["mqtt"]
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="kiosk-display-agent")
    auth = broker.get("auth") or {}
    if auth.get("user"):
        client.username_pw_set(auth["user"], auth.get("pass"))
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(broker["server"], int(broker.get("port", 1883)), keepalive=60)
    client.loop_forever()


if __name__ == "__main__":
    main()
