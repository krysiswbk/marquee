"""Translate a selected item into the existing renderer contract, without policy."""

from typing import Any

from ..signals.model import Signal


def present(item: dict[str, Any], signal: Signal) -> dict[str, Any]:
    attributes = signal.attributes
    context = dict(attributes) if item["renderer"] in ("source", "image", "radar") else {}
    context.update(
        id=item["id"],
        source="attention",
        title=item["title"] or attributes.get("title", "Attention"),
        detail=item["summary"] or attributes.get("detail", ""),
        subtitle=attributes.get("friendly_name", ""),
        status=item["urgency"].title(),
        priority=item["score"],
        accent="#ef4444" if item["urgency"] == "CRITICAL" else "#f59e0b",
    )
    context.setdefault("type", "household_attention")
    if item["renderer"] == "attention":
        context.update(background="", artwork="", rows=[])
    return {
        "playing": True,
        "key": item["id"],
        "type": "media_context",
        "context": context,
        "title": context["title"],
        "subtitle": context["subtitle"],
        "summary": context["detail"],
        "genres": ["HOUSEHOLD"],
        "state": "playing",
        "attention": {
            "id": item["id"],
            "urgency": item["urgency"],
            "acknowledgement_required": item["acknowledgement_required"],
            "acknowledged": item["acknowledged"],
            "members": item["members"],
        },
        "backdrop": bool(context.get("background") or context.get("artwork")),
        "backgroundUrl": context.get("background") or context.get("artwork") or "",
    }
