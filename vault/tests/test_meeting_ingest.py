import pytest

from vault.ingest.meeting_ingest import (
    _fetch_from_supabase,
    normalize_meeting_record,
    build_meeting_entity,
    extract_participants,
    idem_key_for_meeting,
    fetch_and_build,
)
from vault.domain.canonical_types import validate_meeting
from vault.domain.normalize import build_entity_with_traceability


def test_normalize_meeting_record_has_required_contract_fields():
    raw = {
        "meeting_id": "daily-2026-04-10",
        "title": "Daily Status",
        "started_at": "2026-04-10T14:00:00Z",
        "ended_at": "2026-04-10T14:30:00Z",
    }
    result = normalize_meeting_record(raw)

    # Validate the normalizer output by required contract fields,
    # without depending on Meeting validator unknown-field policy
    assert result["id_canonical"] == "meeting:daily-2026-04-10"
    assert result["meeting_id_source"] == "daily-2026-04-10"
    assert result["title"] == "Daily Status"
    assert result["started_at"] == "2026-04-10T14:00:00Z"


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


def test_extract_participants_skips_entries_without_id_and_name():
    raw = {
        "meeting_id": "daily-2026-04-10",
        "participants": [
            {"email": "noid-noname@livingnet.com.br"},
            {"id": "p1", "name": "Robert"},
        ],
    }

    result = extract_participants(raw)

    assert len(result) == 1
    assert result[0]["id"] == "p1"


def test_meeting_entity_has_full_lineage():
    raw = {"meeting_id": "daily-2026-04-10", "title": "Daily"}
    stamped = build_meeting_entity(raw, "wave-c-meeting-ingest-v1")
    assert "source_keys" in stamped
    assert stamped["source_keys"][-1] == "mapper:wave-c-meeting-ingest-v1:meeting:daily-2026-04-10"


def test_normalize_rejects_empty_or_missing_meeting_id():
    with pytest.raises(ValueError, match="meeting_id"):
        normalize_meeting_record({"meeting_id": "", "title": "Daily"})

    with pytest.raises(ValueError, match="meeting_id"):
        normalize_meeting_record({"title": "Daily"})


def test_normalize_rejects_invalid_started_or_ended_at():
    with pytest.raises(ValueError, match="started_at"):
        normalize_meeting_record(
            {
                "meeting_id": "daily-2026-04-10",
                "title": "Daily",
                "started_at": "invalid-date",
            }
        )

    with pytest.raises(ValueError, match="ended_at"):
        normalize_meeting_record(
            {
                "meeting_id": "daily-2026-04-10",
                "title": "Daily",
                "ended_at": "tomorrow maybe",
            }
        )


def test_fetch_and_build_skips_invalid_records(monkeypatch):
    def _fake_fetch(_days):
        return [
            {"meeting_id": "daily-2026-04-10", "title": "ok"},
            {"meeting_id": "", "title": "bad"},
        ]

    monkeypatch.setattr("vault.ingest.meeting_ingest._fetch_from_supabase", _fake_fetch)

    entities, participants = fetch_and_build()

    assert len(entities) == 1
    assert entities[0]["meeting_id_source"] == "daily-2026-04-10"
    assert participants == []


def test_fetch_from_supabase_warns_when_env_missing(monkeypatch, capsys):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)

    result = _fetch_from_supabase()

    out = capsys.readouterr().out
    assert result == []
    assert "[WARN] SUPABASE_URL or key not set; skipping fetch" in out
