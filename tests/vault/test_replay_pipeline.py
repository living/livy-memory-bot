import json
from datetime import datetime, timezone
from pathlib import Path

from vault.ops.replay_pipeline import replay_events


def _write_audit_log(path: Path, events: list[dict]) -> None:
    lines = [json.dumps(e, ensure_ascii=False) for e in events]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_replay_events_processes_only_events_since_cutoff(tmp_path):
    audit_log = tmp_path / "audit.log"
    state = tmp_path / "state.json"

    events = [
        {
            "id": "old-1",
            "entity_id": "topic-1",
            "text": "old",
            "source": "github",
            "author": "bot",
            "event_at": "2026-04-18T23:59:59Z",
        },
        {
            "id": "new-1",
            "entity_id": "topic-2",
            "text": "new",
            "source": "github",
            "author": "bot",
            "event_at": "2026-04-19T00:00:00Z",
        },
    ]
    _write_audit_log(audit_log, events)

    stats = replay_events(
        audit_log_path=audit_log,
        since=datetime(2026, 4, 19, 0, 0, 0, tzinfo=timezone.utc),
        state_path=state,
    )

    assert stats == {"processed": 1, "errors": 0, "total": 2}
    data = json.loads(state.read_text(encoding="utf-8"))
    assert len(data["claims"]) == 1
    assert data["claims"][0]["entity_id"] == "topic-2"


def test_replay_events_counts_errors_for_invalid_event(tmp_path):
    audit_log = tmp_path / "audit.log"
    state = tmp_path / "state.json"

    events = [
        {
            "id": "bad-1",
            # missing event_at on purpose
            "entity_id": "topic-1",
            "text": "bad",
            "source": "github",
            "author": "bot",
        }
    ]
    _write_audit_log(audit_log, events)

    stats = replay_events(
        audit_log_path=audit_log,
        since=datetime(2026, 4, 19, 0, 0, 0, tzinfo=timezone.utc),
        state_path=state,
    )

    assert stats == {"processed": 0, "errors": 1, "total": 1}


def test_replay_events_is_deterministic_for_same_input(tmp_path):
    audit_log = tmp_path / "audit.log"
    state_a = tmp_path / "state-a.json"
    state_b = tmp_path / "state-b.json"

    events = [
        {
            "id": "ev-1",
            "entity_id": "topic-1",
            "text": "x",
            "source": "github",
            "author": "bot",
            "event_at": "2026-04-19T10:00:00Z",
        },
        {
            "id": "ev-2",
            "entity_id": "topic-2",
            "text": "y",
            "source": "trello",
            "author": "bot",
            "event_at": "2026-04-19T10:01:00Z",
        },
    ]
    _write_audit_log(audit_log, events)

    cutoff = datetime(2026, 4, 19, 0, 0, 0, tzinfo=timezone.utc)
    stats_a = replay_events(audit_log, cutoff, state_a)
    stats_b = replay_events(audit_log, cutoff, state_b)

    assert stats_a == stats_b == {"processed": 2, "errors": 0, "total": 2}
    assert state_a.read_text(encoding="utf-8") == state_b.read_text(encoding="utf-8")
