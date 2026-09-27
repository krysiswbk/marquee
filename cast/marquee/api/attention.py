"""Attention API kept separate from legacy HTTP routing."""

import json
from typing import Any

from ..attention.schema import number


def route(handler: Any, services: dict[str, Any], method: str) -> bool:
    path = handler.path.split("?")[0]
    if not path.startswith("/api/attention"):
        return False
    service = services.get("ATTENTION", {}).get("value")
    if service is None:
        handler._send(json.dumps({"error": "attention service is starting"}), "application/json", 503)
        return True
    try:
        if method == "GET" and path == "/api/attention":
            result = service.diagnostics()
        elif method == "GET" and path == "/api/attention/bindings":
            config = service.config
            entities = {b["entity_id"] for b in config["signal_bindings"]}
            entities.update(b["entity_id"] for b in config["context_bindings"].values())
            ttls = [config["signal_ttl"]] + [
                b.get("ttl", config["signal_ttl"])
                for b in config["signal_bindings"] + list(config["context_bindings"].values())
            ]
            attributes = {"friendly_name"} | {
                b["attribute"] for b in config["context_bindings"].values() if "attribute" in b
            }
            result = {
                "entities": sorted(entities),
                "attributes": sorted(attributes),
                "refresh_seconds": min(30, min(ttls) / 3),
            }
        elif method in ("POST", "PUT"):
            length = int(handler.headers.get("Content-Length", "0"))
            if not 0 < length <= 256 * 1024:
                raise ValueError("attention body must be 1..262144 bytes")
            body = json.loads(handler.rfile.read(length))
            if not isinstance(body, dict):
                raise ValueError("attention body must be an object")
            if method == "POST" and path == "/api/attention/signals":
                service.ingest(body)
            elif method == "POST" and path == "/api/attention/action":
                seconds = body.get("seconds", 300)
                number(seconds, 1, 86400, "suppression seconds")
                service.action(str(body.get("id", "")), str(body.get("action", "")), seconds)
            elif method == "POST" and path == "/api/attention/display":
                service.display_state(str(body.get("id", "")), body.get("state", {}))
            elif method == "PUT" and path == "/api/attention/config":
                services["CONFIG_REPOSITORY"].save({"attention": body})
                service.configure(services["CONFIG_REPOSITORY"].effective())
            else:
                handler._send(json.dumps({"error": "not found"}), "application/json", 404)
                return True
            result = {"ok": True}
        else:
            handler._send(json.dumps({"error": "not found"}), "application/json", 404)
            return True
        handler._send(json.dumps(result), "application/json")
    except (ValueError, TypeError, KeyError) as error:
        handler._send(json.dumps({"error": str(error)}), "application/json", 400)
    return True
