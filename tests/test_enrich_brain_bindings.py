"""The HA binding sync preserves existing household policy."""

from integrations.homeassistant.enrich_brain_bindings import BINDINGS, reconciled


def test_room_binding_sync_is_idempotent_and_preserves_existing_policy() -> None:
    current = {"context_bindings": {"guests": {"entity_id": "input_boolean.guest_mode"}},
               "rules": [{"id": "existing"}]}
    desired = reconciled(current)
    assert current["context_bindings"] == {"guests": {"entity_id": "input_boolean.guest_mode"}}
    assert desired["rules"] == current["rules"]
    assert desired["context_bindings"]["guests"] == current["context_bindings"]["guests"]
    assert {name: desired["context_bindings"][name]["entity_id"] for name in BINDINGS} == BINDINGS
    assert reconciled(desired) == desired
