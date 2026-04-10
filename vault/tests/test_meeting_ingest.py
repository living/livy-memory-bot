import pytest

from vault.ingest.meeting_ingest import (
    normalize_meeting_record,
    build_meeting_entity,
    extract_participants,
    idem_key_for_meeting,
)
from vault.domain.canonical_types import validate_meeting
from vault.domain.normalize import build_entity_with_traceability


def test_normalize_meeting_record_strips_id():
    raw = {
        "meeting_id": "daily-2026-04-10",
        "title": "Daily Status",
        "started_at": "2026-04-10T14:00:00Z",
        "ended_at": "2026-04-10T14:30:00Z",
    }
    result = normalize_meeting_record(raw)
    assert result["meeting_id_source"] == "daily-2026-04-10"
    assert result["title"] == "Daily Status"
    assert result["started_at"] == "2026-04-10T14:00:00Z"

    errors = validate_meeting(result)
    if errors is not True:
        required_missing = [e for e in errors if e in ("id_canonical", "meeting_id_source")]
        assert not required_missing, f"required fields missing: {required_missing}"


def test_idem_key_uses_source_key_pattern():
    raw = {"meeting_id": "daily-2026-04-10", "title": "Daily"}
    entity = normalize_meeting_record(raw)
    stamped = build_entity_with_traceability(entity, "wave-c-meeting-ingest-v1")
    key = idem_key_for_meeting(stamped)
    assert key == "tldv:daily-2026-04-10"


def test_extract_participants_returns_list():
    raw = {
        "meeting_id": "daily-2026-04-10",
        "title": "Daily",
        "participants": [
            {"id": "p1", "name": "Robert", "email": "robert@livingnet.com.br"},
            {"id": "p2", "name": "Lincoln", "email": "lincoln@livingnet.com.br"},
        ],
    }
    result = extract_participants(raw)
    assert len(result) == 2
    assert result[0]["source_key"] == "tldv:participant:daily-2026-04-10:p1"


def test_meeting_entity_has_full_lineage():
    raw = {"meeting_id": "daily-2026-04-10", "title": "Daily"}
    stamped = build_meeting_entity(raw, "wave-c-meeting-ingest-v1")
    assert "source_keys" in stamped
    assert stamped["source_keys"][-1] == "mapper:wave-c-meeting-ingest-v1:meeting:daily-2026-04-10"
