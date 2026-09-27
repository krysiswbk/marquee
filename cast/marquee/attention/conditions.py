"""Small declarative predicate language; no expressions or executable templates."""

import math
from typing import Any

OPS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "exists"}
ROOTS = {"signal", "context", "display", "competition", "item"}


def validate_condition(value: Any, depth: int = 0) -> None:
    if not isinstance(value, dict) or depth > 8:
        raise ValueError("condition must be an object with depth <= 8")
    for combinator in ("all", "any", "not"):
        if combinator in value:
            if set(value) != {combinator}:
                raise ValueError("condition combinators cannot have sibling fields")
            children = [value[combinator]] if combinator == "not" else value[combinator]
            if not isinstance(children, list) or not 1 <= len(children) <= 32:
                raise ValueError("condition requires 1..32 children")
            for child in children:
                validate_condition(child, depth + 1)
            return
    if set(value) != {"field", "op", "value"}:
        raise ValueError("condition requires field, op, value")
    path = value["field"]
    if not isinstance(path, str) or path.split(".")[0] not in ROOTS or len(path) > 160:
        raise ValueError("condition field must use signal/context/display/competition/item")
    if value["op"] not in OPS:
        raise ValueError("unsupported condition operator")
    if value["op"] == "exists" and not isinstance(value["value"], bool):
        raise ValueError("exists requires a boolean")
    if value["op"] == "in" and not isinstance(value["value"], list):
        raise ValueError("in condition requires a list")


def matches(condition: dict[str, Any] | None, env: dict[str, Any]) -> bool:
    if condition is None:
        return True
    if "all" in condition:
        return all(matches(c, env) for c in condition["all"])
    if "any" in condition:
        return any(matches(c, env) for c in condition["any"])
    if "not" in condition:
        return not matches(condition["not"], env)
    value: Any = env
    for segment in condition["field"].split("."):
        value = value.get(segment) if isinstance(value, dict) else None
    op, expected = condition["op"], condition["value"]
    if op == "exists":
        return bool((value is not None) == expected)
    # Unknown must not accidentally imply away, healthy, or an inequality.
    if value is None:
        return False
    if op == "eq":
        return bool(value == expected)
    if op == "ne":
        return bool(value != expected)
    if op == "in":
        return value in expected
    if (
        not isinstance(value, (int, float))
        or not isinstance(expected, (int, float))
        or not math.isfinite(value)
        or not math.isfinite(expected)
    ):
        return False
    return {
        "gt": value > expected,
        "gte": value >= expected,
        "lt": value < expected,
        "lte": value <= expected,
    }.get(op, False)
