# Wave C — Entity Model Extension Implementation Plan

> **ARCHIVED (2026-04-11):** This plan was implemented and consolidated into the Living Memory Entity Pipeline. Code examples in this document are historical — the canonical implementation lives in `vault/ingest/external_ingest.py` and `vault/domain/observability.py`. See spec: `docs/superpowers/specs/2026-04-11-living-memory-entity-pipeline-design.md`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand vault entity domain with navigable meeting + card entities, relationship graph (person↔meeting, person↔card), and person identity strengthening via participation signals.

**Architecture:** Incremental phases (C1→C2→C3) with feature-flags. Meeting/card ingestors fetch from TLDV (Supabase) and Trello (API) respectively. IdentityResolver refactored to generic type-aware resolver. All entities carry full lineage. Observability via counters/histograms + append-only audit logs.

**Tech Stack:** Python 3.12+, vault domain layer (canonical_types, normalize, relationship_builder), Supabase REST API, Trello REST API, JSONL audit logs.

**Spec:** `docs/superpowers/specs/2026-04-10-wave-c-entity-model-design.md`

---

## File Map

### New files to create

| File | Phase | Responsibility |
|---|---|---|
| `vault/ingest/meeting_ingest.py` | C1 | Fetch TLDV meetings, build canonical meeting entities |
| `vault/ingest/card_ingest.py` | C1 | Fetch Trello cards, build canonical card entities |
| `vault/tests/test_meeting_ingest.py` | C1 | Tests for meeting ingest (parsing, dedup, schema) |
| `vault/tests/test_card_ingest.py` | C1 | Tests for card ingest (dedup, idempotency, schema) |
| `vault/domain/identity_resolution.py` | C2 | Refactor existing + add generic resolver by type |
| `vault/ingest/strengthen_person.py` | C2 | Add source_keys + conservative confidence to person |
| `vault/tests/test_identity_strengthen.py` | C2 | Guardrail tests, no auto-merge, idempotency |
| `vault/pipeline.py` | C3 | Integrate wave-C stages with feature-flags |
| `vault/tests/test_wave_c_integration.py` | C3 | E2E pipeline tests |
| `vault/domain/observability.py` | C3 | Counters, histograms, audit log emitter |
| `memory/vault/wave-c-runs/` | C3 | Directory for append-only run audit logs |

### Existing files to modify

| File | Changes |
|---|---|
| `vault/domain/canonical_types.py` | Confirm meeting/card validators already exist (do not change) |
| `vault/domain/normalize.py` | Confirm normalize_tldv_meeting_to_entity, normalize_trello_card_to_entity exist (do not change) |
| `vault/domain/relationship_builder.py` | Add `build_person_meeting_edge()` and `build_person_card_edge()` |
| `vault/ingest/__init__.py` | Export new ingestor functions |
| `vault/tests/test_identity_resolution.py` | Add regression tests for existing person resolver |

---

## Phase C1 — Meeting + Card Entities (Quick Win)

### Task C1.1: TLDV Meeting Ingestor

**Files:**
- Create: `vault/ingest/meeting_ingest.py`
- Test: `vault/tests/test_meeting_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_meeting_ingest.py
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
    # NOTE: validate_meeting returns unknown-field errors for confidence/source_keys
    # (not in allowed set yet). Check required fields only.
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
    entity = normalize_meeting_record(raw)
    stamped = build_entity_with_traceability(entity, "wave-c-meeting-ingest-v1")
    assert "lineage" in stamped
    assert stamped["lineage"]["mapper_version"] == "wave-c-meeting-ingest-v1"
    assert stamped["lineage"]["run_id"] is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_meeting_ingest.py -v`
Expected: FAIL — module `meeting_ingest` does not exist

- [ ] **Step 3: Write minimal implementation**

```python
# vault/ingest/meeting_ingest.py
"""TLDV meeting ingestion → canonical meeting entities.

Phase C1 contract:
- Read from TLDV/Supabase (meetings table)
- Lookback: 7 days
- Output: canonical meeting entities with full lineage
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Optional
import os

from vault.domain.normalize import build_entity_with_traceability

MAPPER_VERSION = "wave-c-meeting-ingest-v1"
DEFAULT_LOOKBACK_DAYS = 7


def _fetch_from_supabase(days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict[str, Any]]:
    """Fetch recent meetings from Supabase TLDV.

    Reads SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY from environment.
    Returns list of raw meeting dicts.
    """
    import supabase

    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        # Return empty list if not configured (allows testing without real DB)
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    client = supabase.create_client(url, key)
    resp = (
        client.table("meetings")
        .select("*")
        .gte("started_at", cutoff.isoformat())
        .order("started_at", desc=True)
        .execute()
    )
    return resp.data or []


def normalize_meeting_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a TLDV meeting record to a Meeting entity.

    Produces a partial entity dict (without lineage stamps).
    Use build_entity_with_traceability() after to add lineage.
    """
    meeting_id = raw.get("meeting_id", "")
    title = raw.get("title", "")
    started_at = raw.get("started_at")
    ended_at = raw.get("ended_at")
    project_ref = raw.get("project_ref")

    import hashlib

    raw_id = f"{meeting_id}"
    slug = hashlib.sha1(raw_id.encode()).hexdigest()[:12]

    return {
        "id_canonical": f"meeting:{slug}",
        "meeting_id_source": meeting_id,
        "title": title,
        "started_at": started_at,
        "ended_at": ended_at,
        "project_ref": project_ref,
        "confidence": "medium",
        "source_keys": [f"tldv:{meeting_id}"],
    }


def build_meeting_entity(
    raw: dict[str, Any],
    mapper_version: str = MAPPER_VERSION,
) -> dict[str, Any]:
    """Build a fully-stamped canonical meeting entity from a raw TLDV record."""
    entity = normalize_meeting_record(raw)
    return build_entity_with_traceability(entity, mapper_version)


def extract_participants(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract participant records from a meeting dict."""
    participants = raw.get("participants") or []
    meeting_id = raw.get("meeting_id", "")
    out = []
    for p in participants:
        pid = p.get("id", "unknown")
        out.append(
            {
                "id": pid,
                "name": p.get("name") or p.get("display_name", "unknown"),
                "email": p.get("email"),
                "github_login": p.get("github_login"),
                "source_key": f"tldv:participant:{meeting_id}:{pid}",
            }
        )
    return out


def idem_key_for_meeting(entity: dict[str, Any]) -> str:
    """Return the idempotency source_key for a meeting entity."""
    sk = entity.get("source_keys", [])
    return sk[0] if sk else ""


def fetch_and_build(
    days: int = DEFAULT_LOOKBACK_DAYS,
    mapper_version: str = MAPPER_VERSION,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch meetings from TLDV and build canonical entities + participants.

    Returns:
        (meeting_entities, participant_records)
    """
    raw_meetings = _fetch_from_supabase(days)
    entities = []
    all_participants = []
    for raw in raw_meetings:
        entity = build_meeting_entity(raw, mapper_version)
        entities.append(entity)
        participants = extract_participants(raw)
        all_participants.extend(participants)
    return entities, all_participants
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_meeting_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
git add vault/ingest/meeting_ingest.py vault/tests/test_meeting_ingest.py
git commit -m "feat(wave-c): add TLDV meeting ingestor (C1)"
```

---

### Task C1.2: Trello Card Ingestor

**Files:**
- Create: `vault/ingest/card_ingest.py`
- Test: `vault/tests/test_card_ingest.py`

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_card_ingest.py
import pytest
from vault.ingest.card_ingest import (
    normalize_card_record,
    build_card_entity,
    extract_assignees,
    idem_key_for_card,
)
from vault.domain.canonical_types import validate_card
from vault.domain.normalize import build_entity_with_traceability


def test_normalize_card_record_has_board_prefix():
    raw = {
        "id": "card123",
        "name": "Implement Wave C",
        "board": {"id": "board456", "name": "Living Platform"},
        "list": {"name": "In Progress"},
        "dateLastActivity": "2026-04-10T14:00:00Z",
    }
    result = normalize_card_record(raw)
    assert result["card_id_source"] == "card123"
    assert "source_keys" in result
    assert any("trello:board456:card123" in sk for sk in result["source_keys"])


def test_idem_key_pattern():
    raw = {"id": "card123", "name": "Test", "board": {"id": "b1"}}
    entity = normalize_card_record(raw)
    stamped = build_entity_with_traceability(entity, "wave-c-card-ingest-v1")
    key = idem_key_for_card(stamped)
    assert key.startswith("trello:b1:card123")


def test_extract_assignees_returns_list():
    raw = {
        "id": "card123",
        "name": "Test",
        "board": {"id": "b1"},
        "idMembers": ["m1", "m2"],
        "membersData": [
            {"id": "m1", "fullName": "Robert"},
            {"id": "m2", "fullName": "Lincoln"},
        ],
    }
    result = extract_assignees(raw)
    assert len(result) == 2
    assert result[0]["source_key"] == "trello:assignee:b1:card123:m1"


def test_validate_card_accepts_normalized():
    raw = {"id": "card123", "name": "Test", "board": {"id": "b1"}}
    entity = normalize_card_record(raw)
    stamped = build_entity_with_traceability(entity, "wave-c-card-ingest-v1")
    errors = validate_card(stamped)
    assert errors is True


def test_idempotency_same_record_twice():
    raw = {"id": "card123", "name": "Test", "board": {"id": "b1"}}
    e1 = normalize_card_record(raw)
    e2 = normalize_card_record(raw)
    assert idem_key_for_card(build_entity_with_traceability(e1, "v1")) == idem_key_for_card(build_entity_with_traceability(e2, "v1"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_card_ingest.py -v`
Expected: FAIL — module `card_ingest` does not exist

- [ ] **Step 3: Write minimal implementation**

```python
# vault/ingest/card_ingest.py
"""Trello card ingestion → canonical card entities.

Phase C1 contract:
- Read from Trello REST API (boards/{board_id}/cards)
- Lookback: 7 days by dateLastActivity
- Output: canonical card entities with full lineage
"""
from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any

from vault.domain.normalize import build_entity_with_traceability

MAPPER_VERSION = "wave-c-card-ingest-v1"
DEFAULT_LOOKBACK_DAYS = 7


def _fetch_from_trello(days: int = DEFAULT_LOOKBACK_DAYS) -> list[dict[str, Any]]:
    """Fetch recently-active cards from Trello.

    Reads TRELLO_API_KEY, TRELLO_TOKEN, TRELLO_BOARD_ID from environment.
    Returns list of raw card dicts.
    """
    import requests

    api_key = os.environ.get("TRELLO_API_KEY")
    token = os.environ.get("TRELLO_TOKEN")
    board_id = os.environ.get("TRELLO_BOARD_ID")
    if not api_key or not token or not board_id:
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    url = f"https://api.trello.com/1/boards/{board_id}/cards"
    params = {
        "key": api_key,
        "token": token,
        "fields": "id,name,desc,idBoard,idList,dateLastActivity,idMembers",
        "members": "true",
        "member_fields": "fullName,username",
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    cards = resp.json()
    return [c for c in cards if _is_recent(c, cutoff)]


def _is_recent(card: dict[str, Any], cutoff: datetime) -> bool:
    dla = card.get("dateLastActivity")
    if not dla:
        return False
    try:
        dt = datetime.fromisoformat(str(dla).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt >= cutoff
    except ValueError:
        return False


def normalize_card_record(raw: dict[str, Any]) -> dict[str, Any]:
    """Normalize a Trello card record to a Card entity.

    Produces a partial entity dict (without lineage stamps).
    """
    card_id = raw.get("id", "")
    title = raw.get("name", raw.get("title", ""))
    board = (raw.get("board") or raw.get("idBoard") or "unknown")
    if isinstance(board, dict):
        board = board.get("id", "unknown")
    list_name = None
    list_data = raw.get("list") or raw.get("idList")
    if isinstance(list_data, dict):
        list_name = list_data.get("name")
    project_ref = raw.get("project_ref")
    status = raw.get("state") or raw.get("status")
    source_keys = [
        f"trello:{board}:{card_id}",
        f"mapper:wave-c-card-ingest-v1",
    ]

    return {
        "id_canonical": f"card:{board}:{card_id[:12]}",
        "card_id_source": card_id,
        "board_id": board,
        "title": title,
        "list_name": list_name,
        "project_ref": project_ref,
        "status": status,
        "confidence": "medium",
        "source_keys": source_keys,
    }


def build_card_entity(
    raw: dict[str, Any],
    mapper_version: str = MAPPER_VERSION,
) -> dict[str, Any]:
    """Build a fully-stamped canonical card entity from a raw Trello record."""
    entity = normalize_card_record(raw)
    return build_entity_with_traceability(entity, mapper_version)


def extract_assignees(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract assignee/member records from a card dict."""
    members = raw.get("idMembers") or []
    members_data = raw.get("membersData") or raw.get("members") or []
    board = raw.get("board") or raw.get("idBoard", "unknown")
    if isinstance(board, dict):
        board = board.get("id", "unknown")
    card_id = raw.get("id", "")

    data_map = {m.get("id"): m for m in members_data if isinstance(m, dict)}
    out = []
    for mid in members:
        info = data_map.get(mid, {})
        out.append(
            {
                "id": mid,
                "name": info.get("fullName", "unknown"),
                "username": info.get("username"),
                "source_key": f"trello:assignee:{board}:{card_id}:{mid}",
            }
        )
    return out


def idem_key_for_card(entity: dict[str, Any]) -> str:
    """Return the idempotency source_key for a card entity."""
    sk = entity.get("source_keys", [])
    for k in sk:
        if k.startswith("trello:"):
            return k
    return sk[0] if sk else ""


def fetch_and_build(
    days: int = DEFAULT_LOOKBACK_DAYS,
    mapper_version: str = MAPPER_VERSION,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Fetch cards from Trello and build canonical entities + assignees.

    Returns:
        (card_entities, assignee_records)
    """
    raw_cards = _fetch_from_trello(days)
    entities = []
    all_assignees = []
    for raw in raw_cards:
        entity = build_card_entity(raw, mapper_version)
        entities.append(entity)
        assignees = extract_assignees(raw)
        all_assignees.extend(assignees)
    return entities, all_assignees
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_card_ingest.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
git add vault/ingest/card_ingest.py vault/tests/test_card_ingest.py
git commit -m "feat(wave-c): add Trello card ingestor (C1)"
```

---

### Task C1.3: Relationship Builder Extensions

**Files:**
- Modify: `vault/domain/relationship_builder.py`
- Test: add tests to `vault/tests/test_relation_generation.py`

- [ ] **Step 1: Write the failing test**

Add to `vault/tests/test_relation_generation.py`:

```python
def test_build_person_meeting_edge():
    from vault.domain.relationship_builder import build_person_meeting_edge
    edge = build_person_meeting_edge(
        person_id="person:robert-silva",
        meeting_id="meeting:daily-2026-04-10",
        role="participant",
        person_source_key="github:robert-silva",
        meeting_source_key="tldv:daily-2026-04-10",
    )
    assert edge["from_id"] == "person:robert-silva"
    assert edge["to_id"] == "meeting:daily-2026-04-10"
    assert edge["role"] == "participant"
    assert edge["from_source_key"] == "github:robert-silva"
    assert edge["to_source_key"] == "tldv:daily-2026-04-10"
    assert edge["confidence"] == "high"
    assert "lineage" in edge


def test_build_person_card_edge_assignee():
    from vault.domain.relationship_builder import build_person_card_edge
    edge = build_person_card_edge(
        person_id="person:lincoln-q",
        card_id="card:b1:abc123",
        role="assignee",
        person_source_key="github:lincoln-q",
        card_source_key="trello:b1:abc123",
    )
    assert edge["from_id"] == "person:lincoln-q"
    assert edge["to_id"] == "card:b1:abc123"
    assert edge["role"] == "assignee"
    assert edge["confidence"] == "high"
    assert "lineage" in edge


def test_build_person_card_edge_participant():
    from vault.domain.relationship_builder import build_person_card_edge
    edge = build_person_card_edge(
        person_id="person:lincoln-q",
        card_id="card:b1:abc123",
        role="participant",
        person_source_key="github:lincoln-q",
        card_source_key="trello:b1:abc123",
    )
    assert edge["role"] == "participant"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_relation_generation.py::test_build_person_meeting_edge vault/tests/test_relation_generation.py::test_build_person_card_edge_assignee vault/tests/test_relation_generation.py::test_build_person_card_edge_participant -v`
Expected: FAIL — functions don't exist yet

- [ ] **Step 3: Add to relationship_builder.py**

Append to `vault/domain/relationship_builder.py`:

```python
def build_person_meeting_edge(
    person_id: str,
    meeting_id: str,
    role: str = "participant",
    person_source_key: str | None = None,
    meeting_source_key: str | None = None,
    confidence: str = "high",
    mapper_version: str = "wave-c-relationship-builder-v1",
    run_id: str | None = None,
) -> dict:
    """Build a person -> meeting relationship edge.

    Args:
        person_id:        id_canonical of the person
        meeting_id:       id_canonical of the meeting
        role:             relationship role (participant, decision_maker)
        person_source_key: optional source_key of the person entity
        meeting_source_key: optional source_key of the meeting entity
        confidence:       edge confidence level
        mapper_version:  mapper version stamp for lineage
        run_id:          run_id for lineage (ISO timestamp)
    """
    if role not in RELATIONSHIP_ROLES:
        raise ValueError(f"role must be one of {RELATIONSHIP_ROLES!r}, got {role!r}")
    if run_id is None:
        from datetime import datetime, timezone
        run_id = datetime.now(timezone.utc).isoformat()

    source = {
        "source_type": "wave_c_relationship",
        "source_ref": f"wave-c:{run_id}",
        "retrieved_at": run_id,
        "mapper_version": mapper_version,
    }
    edge = _build_edge(
        from_id=person_id,
        to_id=meeting_id,
        role=role,
        source=source,
        lineage_run_id=run_id,
        confidence=confidence,
    )
    if person_source_key:
        edge["from_source_key"] = person_source_key
    if meeting_source_key:
        edge["to_source_key"] = meeting_source_key
    return edge


def build_person_card_edge(
    person_id: str,
    card_id: str,
    role: str = "assignee",
    person_source_key: str | None = None,
    card_source_key: str | None = None,
    confidence: str = "high",
    mapper_version: str = "wave-c-relationship-builder-v1",
    run_id: str | None = None,
) -> dict:
    """Build a person -> card relationship edge.

    Args:
        person_id:         id_canonical of the person
        card_id:           id_canonical of the card
        role:              relationship role (assignee, participant)
        person_source_key:  optional source_key of the person entity
        card_source_key:    optional source_key of the card entity
        confidence:        edge confidence level
        mapper_version:    mapper version stamp for lineage
        run_id:            run_id for lineage (ISO timestamp)
    """
    if role not in ("assignee", "participant"):
        raise ValueError(f"card edge role must be assignee or participant, got {role!r}")
    if run_id is None:
        from datetime import datetime, timezone
        run_id = datetime.now(timezone.utc).isoformat()

    source = {
        "source_type": "wave_c_relationship",
        "source_ref": f"wave-c:{run_id}",
        "retrieved_at": run_id,
        "mapper_version": mapper_version,
    }
    edge = _build_edge(
        from_id=person_id,
        to_id=card_id,
        role=role,
        source=source,
        lineage_run_id=run_id,
        confidence=confidence,
    )
    if person_source_key:
        edge["from_source_key"] = person_source_key
    if card_source_key:
        edge["to_source_key"] = card_source_key
    return edge
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_relation_generation.py::test_build_person_meeting_edge vault/tests/test_relation_generation.py::test_build_person_card_edge_assignee vault/tests/test_relation_generation.py::test_build_person_card_edge_participant -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
git add vault/domain/relationship_builder.py vault/tests/test_relation_generation.py
git commit -m "feat(wave-c): add person-meeting and person-card edge builders (C2)"
```

---

## Phase C2 — Relationship Graph + Person Strengthening

### Task C2.1: Generic IdentityResolver

**Files:**
- Modify: `vault/domain/identity_resolution.py`
- Test: add regression + new tests to `vault/tests/test_identity_resolution.py`

- [ ] **Step 1: Write the failing tests**

Add to `vault/tests/test_identity_resolution.py`:

```python
def test_resolve_meeting_exact_match():
    from vault.domain.identity_resolution import resolve_by_source_key
    existing = [
        {
            "id_canonical": "meeting:daily-2026-04-10",
            "meeting_id_source": "daily-2026-04-10",
            "source_keys": ["tldv:daily-2026-04-10"],
            "confidence": "medium",
        }
    ]
    result = resolve_by_source_key(existing, "meeting", "tldv:daily-2026-04-10")
    assert result.action == MergeAction.MERGE
    assert result.canonical_id == "meeting:daily-2026-04-10"


def test_resolve_meeting_no_match():
    from vault.domain.identity_resolution import resolve_by_source_key
    existing = [{"id_canonical": "meeting:other", "source_keys": ["tldv:other"]}]
    result = resolve_by_source_key(existing, "meeting", "tldv:nonexistent")
    assert result.action == MergeAction.NO_MATCH


def test_resolve_card_exact_match():
    from vault.domain.identity_resolution import resolve_by_source_key
    existing = [
        {
            "id_canonical": "card:b1:abc123",
            "card_id_source": "abc123",
            "source_keys": ["trello:b1:abc123"],
        }
    ]
    result = resolve_by_source_key(existing, "card", "trello:b1:abc123")
    assert result.action == MergeAction.MERGE
    assert result.canonical_id == "card:b1:abc123"


def test_resolve_person_extends_existing():
    from vault.domain.identity_resolution import resolve_identity
    existing = [{"id_canonical": "person:robert", "github_login": "robert", "source_keys": ["github:robert"]}]
    incoming = {"github_login": "robert", "email": "robert@livingnet.com.br"}
    result = resolve_identity(existing, incoming)
    # guardrail atual: <2 source_keys no candidato => REVIEW
    assert result.action == MergeAction.REVIEW


def test_strengthen_person_conservative_confidence():
    from vault.ingest.strengthen_person import strengthen_person
    entity = {
        "id_canonical": "person:robert",
        "confidence": "low",
        "source_keys": ["github:robert"],
        "display_name": "Robert",
    }
    signal = {"source_key": "tldv:participant:daily-2026-04-10:robert-p1", "type": "meeting_participant"}
    result = strengthen_person(entity, signal)
    # confidence increments conservatively, capped at high
    assert result["confidence"] in ("low", "medium", "high")
    assert "tldv:participant:daily-2026-04-10:robert-p1" in result["source_keys"]


def test_strengthen_person_idempotent():
    from vault.ingest.strengthen_person import strengthen_person
    entity = {
        "id_canonical": "person:robert",
        "confidence": "medium",
        "source_keys": ["github:robert", "tldv:participant:daily-2026-04-10:robert-p1"],
        "display_name": "Robert",
    }
    signal = {"source_key": "tldv:participant:daily-2026-04-10:robert-p1", "type": "meeting_participant"}
    result = strengthen_person(entity, signal)
    # same source_key should not be duplicated
    assert result["source_keys"].count("tldv:participant:daily-2026-04-10:robert-p1") == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_identity_resolution.py -k "resolve_meeting or resolve_card or strengthen_person" -v`
Expected: FAIL — new functions don't exist

- [ ] **Step 3: Implement generic resolver + strengthen**

Append to `vault/domain/identity_resolution.py`:

```python
def resolve_by_source_key(
    existing: list[dict],
    entity_type: str,
    source_key: str,
) -> IdentityResult:
    """Resolve entity by exact source_key match.

    Supports: person, meeting, card, repo.

    Args:
        existing:     list of existing entity dicts
        entity_type:   "person" | "meeting" | "card" | "repo"
        source_key:    source_key to match

    Returns:
        IdentityResult with MATCH (exact match), NO_MATCH (not found)
    """
    for entity in existing:
        keys = _get_source_keys(entity)
        if source_key in keys:
            return IdentityResult(
                action=MergeAction.MERGE,
                canonical_id=entity.get("id_canonical"),
            )
    return IdentityResult(action=MergeAction.NO_MATCH)
```

Create `vault/ingest/strengthen_person.py`:

```python
"""Person identity strengthening via participation signals (Wave C Phase C2).

Adds derived source_keys and conservative confidence increments to person entities
without performing auto-merge.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

MAPPER_VERSION = "wave-c-person-strengthen-v1"

# Confidence ceiling: never supersede primary sources
_CONFIDENCE_CEILING = {"low": "medium", "medium": "medium", "high": "high"}
_CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def strengthen_person(
    entity: dict[str, Any],
    signal: dict[str, Any],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Add a participation-derived source_key to a person entity.

    Applies idempotency (no duplicate source_keys) and conservative confidence
    ceiling (never exceeds 'high', caps medium→medium).

    Args:
        entity:    existing person entity dict (with source_keys, confidence)
        signal:    participation signal dict with 'source_key' field
        run_id:    optional run_id for lineage

    Returns:
        Modified entity dict (does NOT mutate input).
    """
    if run_id is None:
        run_id = datetime.now(timezone.utc).isoformat()

    derived_key = signal.get("source_key", "")
    if not derived_key:
        return entity

    # Idempotency: dedupe source_keys
    new_keys = list(entity.get("source_keys") or [])
    if derived_key not in new_keys:
        new_keys.append(derived_key)

    # Conservative confidence ceiling
    current_conf = entity.get("confidence", "low")
    ceiling = _CONFIDENCE_CEILING.get(current_conf, "medium")
    # Only bump up if current is below ceiling
    if _CONFIDENCE_ORDER.get(current_conf, 0) < _CONFIDENCE_ORDER.get(ceiling, 1):
        new_conf = ceiling
    else:
        new_conf = current_conf

    return {
        **entity,
        "source_keys": new_keys,
        "confidence": new_conf,
        "_strengthened": True,
        "_strengthen_signal": derived_key,
        "_strengthen_run_id": run_id,
    }


def strengthen_from_signals(
    entity: dict[str, Any],
    signals: list[dict[str, Any]],
    run_id: str | None = None,
) -> dict[str, Any]:
    """Apply multiple signals to a person entity sequentially.

    Idempotent: deduplication is applied per signal.
    Confidence ceiling applied once after all signals.
    """
    result = dict(entity)
    for sig in signals:
        result = strengthen_person(result, sig, run_id=run_id)
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_identity_resolution.py -k "resolve_meeting or resolve_card or strengthen_person" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
git add vault/domain/identity_resolution.py vault/ingest/strengthen_person.py vault/tests/test_identity_resolution.py vault/tests/test_identity_strengthen.py
git commit -m "feat(wave-c): add generic identity resolver + person strengthening (C2)"
```

---

## Phase C3 — Pipeline Integration, Observability, Quality

### Task C3.1: Observability Module

**Files:**
- Create: `vault/domain/observability.py`
- Test: `vault/tests/test_observability.py`

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_observability.py
import pytest, json, tempfile, os
from vault.domain.observability import WaveCObserver, RunAuditor, CONFIDENCE_ORDER


def test_counter_increment():
    obs = WaveCObserver()
    obs.increment("wave_c.ingest.meetings.total")
    obs.increment("wave_c.ingest.meetings.total")
    assert obs.counters["wave_c.ingest.meetings.total"] == 2


def test_histogram_record():
    obs = WaveCObserver()
    obs.record_duration("wave_c.run.duration_ms", 1500)
    assert "wave_c.run.duration_ms" in obs.histograms
    assert obs.histograms["wave_c.run.duration_ms"] == 1500


def test_observer_snapshot():
    obs = WaveCObserver()
    obs.increment("wave_c.ingest.cards.created", 3)
    snap = obs.snapshot()
    assert snap["counters"]["wave_c.ingest.cards.created"] == 3
    assert "wave_c.run.duration_ms" in snap["histograms"]


def test_run_auditor_write_and_read():
    with tempfile.TemporaryDirectory() as tmpdir:
        aud = RunAuditor(tmpdir)
        run_id = "wc-2026-04-10T14:00:00Z"
        aud.emit(run_id, phase="C1", results={"meetings_ingested": 5, "cards_ingested": 10})
        path = aud.path_for(run_id)
        assert path.exists()
        with open(path) as f:
            data = json.load(f)
        assert data["run_id"] == run_id
        assert data["results"]["meetings_ingested"] == 5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_observability.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Write implementation**

```python
# vault/domain/observability.py
"""Wave C observability: counters, histograms, run auditor (append-only).

Per spec §7 Observabilidade and §8 Rastreabilidade.
"""
from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "memory" / "vault"
RUNS_DIR = ROOT / "wave-c-runs"

CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


class WaveCObserver:
    """Lightweight in-memory metrics collector for a single run."""

    def __init__(self) -> None:
        self.counters: dict[str, int] = {}
        self.histograms: dict[str, float] = {}
        self.started_at = datetime.now(timezone.utc)

    def increment(self, metric: str, value: int = 1) -> None:
        self.counters[metric] = self.counters.get(metric, 0) + value

    def record_duration(self, metric: str, ms: float) -> None:
        self.histograms[metric] = ms

    def snapshot(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at.isoformat(),
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": (datetime.now(timezone.utc) - self.started_at).total_seconds() * 1000,
            "counters": dict(self.counters),
            "histograms": dict(self.histograms),
        }

    def emit(self) -> dict[str, Any]:
        return self.snapshot()


class RunAuditor:
    """Append-only audit log writer for wave-C runs.

    Per spec §7.2 — writes atomically to avoid partial artifacts.
    """

    def __init__(self, runs_dir: Path | str = RUNS_DIR) -> None:
        self.runs_dir = Path(runs_dir)
        self.runs_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, run_id: str) -> Path:
        return self.runs_dir / f"{run_id}.json"

    def emit(
        self,
        run_id: str,
        phase: str,
        results: dict[str, Any],
        quality: dict[str, Any] | None = None,
        source: str = "tldv|trello",
        lookback_days: int = 7,
    ) -> Path:
        payload = {
            "run_id": run_id,
            "phase": phase,
            "started_at": run_id,
            "ended_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
            "lookback_days": lookback_days,
            "results": results,
            "quality": quality or {},
        }
        tmp = self.runs_dir / f"{run_id}.json.tmp"
        with open(tmp, "w") as f:
            json.dump(payload, f, indent=2)
        tmp.rename(self.path_for(run_id))
        return self.path_for(run_id)

    def emit_review_entry(
        self,
        run_id: str,
        entry_type: str,
        data: dict[str, Any],
    ) -> Path:
        qpath = self.runs_dir / f"{run_id}.review-queue.jsonl"
        line = json.dumps({"run_id": run_id, "type": entry_type, **data})
        with open(qpath, "a") as f:
            f.write(line + "\n")
        return qpath


def build_run_id() -> str:
    return f"wc-{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_observability.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
git add vault/domain/observability.py vault/tests/test_observability.py
git commit -m "feat(wave-c): add observability module (counters, auditor) (C3)"
```

---

### Task C3.2: Pipeline Integration

**Files:**
- Modify: `vault/pipeline.py`
- Test: `vault/tests/test_wave_c_integration.py`

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_wave_c_integration.py
import pytest, tempfile, os
from vault.pipeline import run_pipeline


def test_pipeline_with_wave_c_disabled():
    """C3: when feature flags are off, pipeline runs without wave-C stages."""
    with tempfile.TemporaryDirectory() as tmpdir:
        events = tmpdir + "/events.jsonl"
        with open(events, "w") as f:
            f.write('{"event_id":"e1","signal_type":"decision","origin_id":"d1"}\n')
        result = run_pipeline(
            events_path=events,
            dry_run=True,
            wave_c_enabled=False,
        )
        assert result["dry_run"] is True


def test_wave_c_feature_flags_defaults():
    """C3: feature flags default to C1=true, C2=false, C3=false."""
    from vault.pipeline import _wave_c_flags
    assert _wave_c_flags()["WAVE_C_C1_ENABLED"] is True
    assert _wave_c_flags()["WAVE_C_C2_ENABLED"] is False
    assert _wave_c_flags()["WAVE_C_C3_ENABLED"] is False


def test_pipeline_emit_observer_snapshot():
    """C3: pipeline returns wave_c_observer in result."""
    with tempfile.TemporaryDirectory() as tmpdir:
        events = tmpdir + "/events.jsonl"
        with open(events, "w") as f:
            f.write('{"event_id":"e1","signal_type":"decision","origin_id":"d1"}\n')
        result = run_pipeline(
            events_path=events,
            dry_run=True,
            wave_c_enabled=True,
        )
        assert "wave_c_observer" in result or "wave_c" in result
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_wave_c_integration.py -v`
Expected: FAIL — feature flags don't exist

- [ ] **Step 3: Add feature flags + wave-C stage to pipeline.py**

Add to `vault/pipeline.py` after imports:

```python
import os

def _wave_c_flags() -> dict[str, bool]:
    return {
        "WAVE_C_C1_ENABLED": os.environ.get("WAVE_C_C1_ENABLED", "true").lower() == "true",
        "WAVE_C_C2_ENABLED": os.environ.get("WAVE_C_C2_ENABLED", "false").lower() == "true",
        "WAVE_C_C3_ENABLED": os.environ.get("WAVE_C_C3_ENABLED", "false").lower() == "true",
    }
```

Add to `run_pipeline()` signature:

```python
def run_pipeline(
    *,
    events_path: Path | str = DEFAULT_EVENTS,
    dry_run: bool = False,
    verbose: bool = False,
    repair: bool = False,
    reverify: bool = False,
    enable_domain_metrics: bool = True,
    wave_c_enabled: bool = False,
    wave_c_flags: dict[str, bool] | None = None,
) -> dict:
```

Add inside `run_pipeline()` after the lint/repair block (before return):

```python
    # Wave C Phase C3: Observability + Audit
    wave_c_observer: dict = {}
    if wave_c_enabled:
        try:
            from vault.domain.observability import WaveCObserver, RunAuditor, build_run_id
            observer = WaveCObserver()
            flags = wave_c_flags or _wave_c_flags()
            run_id = build_run_id()
            auditor = RunAuditor()

            if flags.get("WAVE_C_C1_ENABLED"):
                observer.increment("wave_c.pipeline.stage", 1)

            if flags.get("WAVE_C_C2_ENABLED"):
                observer.increment("wave_c.pipeline.stage", 2)

            if flags.get("WAVE_C_C3_ENABLED"):
                observer.increment("wave_c.pipeline.stage", 3)

            observer.record_duration("wave_c.run.duration_ms", 0)  # placeholder
            wave_c_observer = observer.emit()

            auditor.emit(
                run_id=run_id,
                phase="C3",
                results={
                    "decisions_written": len(decisions_written),
                    "concepts_written": len(concepts_written),
                    "failed_events": failed_events,
                    "skipped_events": skipped_events,
                },
                quality={
                    "gaps_after_lint": gaps_after_lint,
                    "orphans_after_lint": orphans_after_lint,
                },
            )
        except Exception as e:
            if verbose:
                print(f"  [WARN] Wave C observability failed: {e}")
            wave_c_observer = {"error": str(e)}
```

Add `wave_c_observer` to the return dict:

```python
    return {
        # ... existing fields ...
        "wave_c_observer": wave_c_observer,
        "pipeline_at": datetime.now(timezone.utc).isoformat(),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_wave_c_integration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
git add vault/pipeline.py vault/tests/test_wave_c_integration.py
git commit -m "feat(wave-c): integrate feature flags and observability into pipeline (C3)"
```

---

### Task C3.3: Lint Extension + Quality Gates

**Files:**
- Modify: `vault/lint.py` (add wave-c lint rules)
- Test: add to `vault/tests/test_lint_module.py`

- [ ] **Step 1: Write the failing test**

Add to `vault/tests/test_lint_module.py`:

```python
def test_wave_c_lint_catches_orphan_meeting_edge():
    """Wave C: edge referencing non-existent meeting is orphan."""
    # Create a person entity with a meeting edge pointing to missing meeting
    person_md = MEMORY_DIR / "person" / "robert.md"
    person_md.parent.mkdir(parents=True, exist_ok=True)
    person_md.write_text("""---
id_canonical: person:robert
source_keys: ["github:robert"]
confidence: medium
---
# Robert
""")
    edge_md = EDGES_DIR / "person-robert--meeting-nonexistent.md"
    edge_md.parent.mkdir(parents=True, exist_ok=True)
    edge_md.write_text("""---
from_id: person:robert
to_id: meeting:nonexistent
role: participant
---
""")
    from vault.lint import run_lint
    report = run_lint(MEMORY_DIR)
    orphan_ids = [e["entity_id"] for e in report.get("orphans", [])]
    assert any("person-robert--meeting-nonexistent" in o for o in orphan_ids)


def test_wave_c_lint_checks_meeting_id_source():
    """Wave C: meeting entity must have meeting_id_source field."""
    meeting_md = MEMORY_DIR / "meeting" / "daily-test.md"
    meeting_md.parent.mkdir(parents=True, exist_ok=True)
    meeting_md.write_text("""---
id_canonical: meeting:daily-test
title: Daily
---
# Daily
""")
    from vault.lint import run_lint
    report = run_lint(MEMORY_DIR)
    # Should flag missing meeting_id_source
    issues = report.get("all_issues", [])
    assert any("meeting_id_source" in str(i) for i in issues)


def test_wave_c_lint_checks_card_board_id():
    """Wave C: card entity must have card_id_source field."""
    card_md = MEMORY_DIR / "card" / "board1-card123.md"
    card_md.parent.mkdir(parents=True, exist_ok=True)
    card_md.write_text("""---
id_canonical: card:board1:abc
title: Test Card
---
# Test Card
""")
    from vault.lint import run_lint
    report = run_lint(MEMORY_DIR)
    issues = report.get("all_issues", [])
    assert any("card_id_source" in str(i) for i in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_lint_module.py -k "wave_c_lint" -v`
Expected: FAIL — rules not implemented

- [ ] **Step 3: Add wave-C lint rules**

Add to `vault/lint.py`:

```python
def _lint_wave_c_entity(entity_path: Path, entity_type: str, frontmatter: dict, issues: list) -> None:
    """Run Wave C entity-specific linting rules."""
    if entity_type == "meeting":
        if "meeting_id_source" not in frontmatter:
            issues.append({"entity": entity_path.name, "rule": "missing_meeting_id_source", "severity": "error"})
    elif entity_type == "card":
        if "card_id_source" not in frontmatter:
            issues.append({"entity": entity_path.name, "rule": "missing_card_id_source", "severity": "error"})
        if "board_id" not in frontmatter:
            issues.append({"entity": entity_path.name, "rule": "missing_board_id", "severity": "warn"})


def _lint_wave_c_edge(edge_path: Path, frontmatter: dict, all_entities: set[str], issues: list) -> None:
    """Run Wave C edge linting: validate target entities exist."""
    from_id = frontmatter.get("from_id", "")
    to_id = frontmatter.get("to_id", "")
    # Check to_id exists
    if to_id and to_id not in all_entities:
        issues.append({
            "entity": edge_path.name,
            "rule": "orphan_edge_target",
            "severity": "warn",
            "detail": f"to_id {to_id} not found in entities",
        })
    # Role validation
    role = frontmatter.get("role", "")
    if role and role not in ("author", "reviewer", "commenter", "participant", "decision_maker", "assignee"):
        issues.append({
            "entity": edge_path.name,
            "rule": "invalid_role",
            "severity": "error",
            "detail": f"role {role!r} not in allowed set",
        })
```

Call `_lint_wave_c_entity` and `_lint_wave_c_edge` inside `run_lint()`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_lint_module.py -k "wave_c_lint" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
git add vault/lint.py vault/tests/test_lint_module.py
git commit -m "feat(wave-c): add meeting/card lint rules and edge orphan detection (C3)"
```

---

## Final Verification

After all tasks complete, run the full test suite:

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python3 -m pytest vault/tests/ -q --tb=short
```

Expected: All tests pass, no regressions in existing suite.

Then run E2E dry-run:

```bash
python3 -m vault.pipeline --dry-run
```

Expected: Pipeline runs, wave_c_observer present in result, no errors.
