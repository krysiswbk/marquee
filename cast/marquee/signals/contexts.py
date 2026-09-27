"""Existing provider contexts become observations, without assigning final priority."""

from datetime import datetime, timezone
from typing import Any

from .model import Signal


def normalize(context: dict[str, Any], now: float) -> Signal:
    expiry = context.get("expires") or context.get("expires_at")
    try:
        stamp = datetime.fromisoformat(str(expiry).replace("Z", "+00:00"))
        expires = stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).timestamp()
    except (ValueError, TypeError):
        expires = now + 90 if not expiry else now
    return Signal(
        id="context:" + str(context["id"]),
        type=str(context.get("type", "context")),
        source=str(context.get("source", "provider")),
        entity_id=str(context["id"]),
        category=str(context.get("subtype") or context.get("source", "ambient")),
        state="active",
        created_at=now,
        updated_at=now,
        active_since=now,
        expires_at=expires,
        priority=float(context.get("priority", 0)),
        attributes=dict(context),
        dedupe_key=str(context["id"]),
    )
