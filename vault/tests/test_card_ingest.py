import pytest

from vault.domain.normalize import build_entity_with_traceability
from vault.ingest.card_ingest import (
    normalize_card_record,
    build_card_entity,
    extract_assignees,
    idem_key_for_card,
)


def test_normalize_card_record_has_board_prefix():
    raw = {
        "id": "card123",
        "name": "Implement Wave C",
        "board": {"id": "board456", "name": "Living Platform"},
        "list": {"name": "In Progress"},
        "dateLastActivity": "2026-04-10T14:00:00Z",
    }

    result = normalize_card_record(raw)

    assert result["id_canonical"] == "card:board456:card123"
    assert result["card_id_source"] == "card123"
    assert result["board"] == "board456"
    assert result["list"] == "In Progress"
    assert "source_keys" in result
    assert "trello:board456:card123" in result["source_keys"]


def test_idem_key_pattern_uses_trello_source_key():
    raw = {"id": "card123", "name": "Test", "board": {"id": "b1"}}

    entity = normalize_card_record(raw)
    stamped = build_entity_with_traceability(entity, "wave-c-card-ingest-v1")

    key = idem_key_for_card(stamped)

    assert key == "trello:b1:card123"


def test_extract_assignees_returns_list():
    raw = {
        "id": "card123",
        "name": "Test",
        "board": {"id": "b1"},
        "idMembers": ["m1", "m2"],
        "membersData": [
            {"id": "m1", "fullName": "Robert", "username": "robert"},
            {"id": "m2", "fullName": "Lincoln", "username": "lincoln"},
        ],
    }

    result = extract_assignees(raw)

    assert len(result) == 2
    assert result[0]["source_key"] == "trello:assignee:b1:card123:m1"
    assert result[1]["source_key"] == "trello:assignee:b1:card123:m2"


def test_build_card_entity_has_full_lineage_stamp():
    raw = {"id": "card123", "name": "Test", "board": {"id": "b1"}}

    stamped = build_card_entity(raw, "wave-c-card-ingest-v1")

    assert "source_keys" in stamped
    assert (
        stamped["source_keys"][-1]
        == "mapper:wave-c-card-ingest-v1:card:b1:card123"
    )
    assert "first_seen_at" in stamped
    assert "last_seen_at" in stamped


def test_normalize_rejects_empty_or_missing_card_id():
    with pytest.raises(ValueError, match="card_id"):
        normalize_card_record({"id": "", "name": "Test", "board": {"id": "b1"}})

    with pytest.raises(ValueError, match="card_id"):
        normalize_card_record({"name": "Test", "board": {"id": "b1"}})


def test_normalize_rejects_missing_board_id():
    with pytest.raises(ValueError, match="board_id"):
        normalize_card_record({"id": "card123", "name": "Test"})


def test_normalize_rejects_invalid_dates():
    with pytest.raises(ValueError, match="dateLastActivity"):
        normalize_card_record(
            {
                "id": "card123",
                "name": "Test",
                "board": {"id": "b1"},
                "dateLastActivity": "not-a-date",
            }
        )


def test_extract_assignees_skips_members_without_identifiers():
    raw = {
        "id": "card123",
        "board": {"id": "b1"},
        "idMembers": ["m1", "", None],
        "membersData": [
            {"id": "m1", "fullName": "Robert"},
            {"fullName": "No Identifier"},
            {"id": "", "fullName": "Empty ID"},
        ],
    }

    result = extract_assignees(raw)

    assert len(result) == 1
    assert result[0]["id"] == "m1"


def test_idempotency_same_record_twice():
    raw = {"id": "card123", "name": "Test", "board": {"id": "b1"}}

    e1 = normalize_card_record(raw)
    e2 = normalize_card_record(raw)

    assert idem_key_for_card(build_entity_with_traceability(e1, "v1")) == idem_key_for_card(
        build_entity_with_traceability(e2, "v1")
    )
