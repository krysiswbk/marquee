"""Small presentation transforms for the Cast ambient lane."""


def calendar_agenda(contexts, limit=5):
    """Collapse ordinary upcoming calendar items into one Cast-sized agenda."""
    items = []
    seen = set()
    for item in contexts:
        if (item.get("type") != "calendar_event" or
                item.get("subtype") == "birthday_rollup" or
                item.get("castTakeover") is True or
                int(item.get("priority", 0)) >= 95 or
                not str(item.get("title", "")).strip()):
            continue
        identity = item.get("id") or (item.get("title"), item.get("starts"))
        if identity in seen:
            continue
        seen.add(identity)
        items.append(item)
    items.sort(key=lambda item: (str(item.get("starts", "")),
                                 str(item.get("title", "")).casefold(),
                                 str(item.get("id", ""))))
    items = items[:max(2, int(limit))]
    if len(items) < 2:
        return None
    rows = [" · ".join(value for value in (item.get("title"),
                                            item.get("subtitle")) if value)
            for item in items]
    rows = [row[:180] for row in rows if row]
    if len(rows) < 2:
        return None
    first = items[0]
    return {
        "id": "calendar:ambient-agenda", "source": "calendar", "provider": "calendar",
        "type": "calendar_event", "subtype": "ambient_agenda",
        "priority": max(int(item.get("priority", 0)) for item in items),
        "relevance": max(int(item.get("relevance", 0)) for item in items),
        "urgency": max(int(item.get("urgency", 0)) for item in items),
        "title": "Upcoming", "subtitle": f"{len(rows)} calendar events", "detail": "",
        "status": "Coming up", "starts": first.get("starts", ""),
        "expires": max((str(item.get("expires", "")) for item in items), default=""),
        "targets": ["kiosk"], "rows": rows, "allDay": False, "location": "",
        "castTakeover": False, "eventState": "UPCOMING",
    }
