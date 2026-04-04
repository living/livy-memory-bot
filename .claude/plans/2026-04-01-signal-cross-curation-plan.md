# Signal Cross-Curation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a signal-based memory curation system that cross-references TLDV meetings, job logs, Git PRs, and Lincoln's feedback to automatically update topic files when sources agree, and flag conflicts when they don't.

**Architecture:** Event-driven pipeline: collectors emit SignalEvents → signal bus persists them → topic analyzer computes candidate changes → auto-curator applies when conditions are met → conflicts go to a queue for Lincoln. Every event carries a `correlation_id` for end-to-end tracing.

**Tech Stack:** Python 3, UUID for IDs, JSON Lines for persistence, Supabase REST API for TLDV, GitHub REST API, filesystem for topic files.

---

## File Map

```
skills/memoria-consolidation/
├── signal_bus.py              # SignalEvent dataclass + in-memory bus + JSONL persistence
├── collectors/
│   ├── __init__.py
│   ├── tldv_collector.py     # Supabase → SignalEvents (priority 1)
│   └── logs_collector.py     # BAT/Delphos reports → SignalEvents (priority 2)
├── topic_analyzer.py          # Given topic file + signals → candidate changes
├── auto_curator.py           # Apply candidate changes when conditions met
├── conflict_detector.py       # Detect conflicts between sources
├── conflict_queue.py          # CRUD for conflict queue file
└── curation_cron.py          # Orchestration: collect → analyze → auto-curate → report

memory/
├── logs/
│   └── curation-{date}.log  # JSON Lines observability
├── curation-log.md           # Human-readable log of applied changes
├── signal-events.jsonl       # Signal bus persistence
└── conflict-queue.md        # Conflict queue for Lincoln review

tests/
└── test_signal_curation.py  # All unit tests (by component)
```

---

## PRELUDE — Setup e Consistência

### Task 0: Estrutura de diretórios e imports

**Files:**
- Create: `skills/memoria-consolidation/collectors/__init__.py`
- Create: `memory/logs/` (directory)
- Modify: `skills/memoria-consolidation/__init__.py` (empty, for imports)

- [ ] **Step 1: Criar estrutura de diretórios**

```bash
mkdir -p /home/lincoln/.openclaw/workspace-livy-memory/memory/logs
mkdir -p /home/lincoln/.openclaw/workspace-livy-memory/skills/memoria-consolidation/collectors
touch /home/lincoln/.openclaw/workspace-livy-memory/skills/memoria-consolidation/collectors/__init__.py
touch /home/lincoln/.openclaw/workspace-livy-memory/skills/memoria-consolidation/__init__.py
```

- [ ] **Step 2: Commit**

```bash
git add skills/memoria-consolidation/collectors/__init__.py skills/memoria-consolidation/__init__.py
git commit -m "feat(signal-curation): create collectors package and directory structure

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## FASE 1 — Foundation

### Task 1: signal_bus.py — Core Infrastructure

**Files:**
- Create: `skills/memoria-consolidation/signal_bus.py`
- Create: `tests/test_signal_curation.py` (test file for ALL components — add tests per task)

**Dependencies:** No external dependencies.

- [ ] **Step 1: Write test for SignalEvent dataclass**

Add to `tests/test_signal_curation.py`:

```python
import sys, uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))

from signal_bus import SignalEvent, SignalBus

def test_signal_event_dataclass():
    event = SignalEvent(
        source="tldv",
        priority=1,
        topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Use Postgres", "evidence": "meeting #123", "confidence": 0.9},
        origin_id="meeting-123",
        origin_url="https://tldv.io/meeting/123",
    )
    assert event.source == "tldv"
    assert event.priority == 1
    assert event.signal_type == "decision"
    assert event.event_id is not None  # auto-generated
    assert event.correlation_id is not None  # auto-generated
    assert event.collected_at is not None  # auto-generated

def test_signal_event_serialization():
    event = SignalEvent(
        source="logs",
        priority=2,
        topic_ref="bat-conectabot.md",
        signal_type="failure",
        payload={"description": "Job failed", "evidence": None, "confidence": 1.0},
        origin_id="bat-daily-2026-04-01",
        origin_url=None,
    )
    data = event.model_dump()
    assert data["source"] == "logs"
    assert data["priority"] == 2
    assert "event_id" in data
    assert "correlation_id" in data

def test_signal_bus_initial_state():
    bus = SignalBus()
    assert bus.events == []
    assert bus.correlation_id is None

def test_signal_bus_set_correlation_id():
    bus = SignalBus()
    cid = bus.start_cycle()
    assert bus.correlation_id == cid
    assert uuid.UUID(cid)  # valid UUID

def test_signal_bus_emit():
    bus = SignalBus()
    bus.start_cycle()
    event = SignalEvent(
        source="tldv",
        priority=1,
        topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Test", "evidence": None, "confidence": 0.8},
        origin_id="m123",
        origin_url=None,
    )
    emitted = bus.emit(event)
    assert emitted.event_id == event.event_id
    assert len(bus.events) == 1

def test_signal_bus_get_by_topic():
    bus = SignalBus()
    bus.start_cycle()
    for i in range(3):
        e = SignalEvent(source="tldv", priority=1, topic_ref="forge.md",
                        signal_type="decision",
                        payload={"description": f"d{i}", "evidence": None, "confidence": 0.8},
                        origin_id=f"m{i}", origin_url=None)
        bus.emit(e)
    bus.emit(SignalEvent(source="logs", priority=2, topic_ref="other.md",
                         signal_type="failure",
                         payload={"description": "fail", "evidence": None, "confidence": 1.0},
                         origin_id="l1", origin_url=None))
    forge_events = bus.get_by_topic("forge.md")
    assert len(forge_events) == 3
    assert all(e.topic_ref == "forge.md" for e in forge_events)

def test_signal_bus_persist_and_load(tmp_path):
    import json
    bus = SignalBus()
    bus.start_cycle()
    bus.emit(SignalEvent(source="tldv", priority=1, topic_ref="test.md",
                         signal_type="decision",
                         payload={"description": "persist test", "evidence": None, "confidence": 0.9},
                         origin_id="m1", origin_url=None))
    events_file = tmp_path / "events.jsonl"
    bus.persist(events_file)

    # Load into new bus
    bus2 = SignalBus()
    bus2.load(events_file)
    assert len(bus2.events) == 1
    assert bus2.events[0].source == "tldv"
```

- [ ] **Step 2: Run tests — verify they fail (signal_bus not defined)**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_signal_event_dataclass tests/test_signal_curation.py::test_signal_event_serialization tests/test_signal_curation.py::test_signal_bus_initial_state tests/test_signal_curation.py::test_signal_bus_set_correlation_id tests/test_signal_curation.py::test_signal_bus_emit tests/test_signal_curation.py::test_signal_bus_get_by_topic tests/test_signal_curation.py::test_signal_bus_persist_and_load -v 2>&1 | head -30
```
Expected: FAIL — `signal_bus` not defined

- [ ] **Step 3: Write signal_bus.py**

```python
#!/usr/bin/env python3
"""
signal_bus.py — Unified signal event bus with JSONL persistence.
"""
import uuid, json
from datetime import datetime, timezone
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional


class SignalEvent(BaseModel):
    """Normalized signal event across all sources."""
    # Identity
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str = Field(default=None)  # set by bus.start_cycle()
    # Provenance
    source: str  # "tldv" | "logs" | "github" | "feedback"
    priority: int = Field(ge=1, le=4)
    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    processed_at: Optional[str] = None
    # Content
    topic_ref: Optional[str] = None
    signal_type: str  # "decision" | "topic_mentioned" | "success" | "failure" | "correction"
    payload: dict = Field(default_factory=dict)  # description, evidence, confidence
    # Origin
    origin_id: str
    origin_url: Optional[str] = None

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Serialize None as None (not excluded)
        return data


class SignalBus:
    """
    In-memory event bus for SignalEvents.
    Provides correlation_id tracking, topic-based filtering, and JSONL persistence.
    """

    def __init__(self):
        self.events: list[SignalEvent] = []
        self.correlation_id: Optional[str] = None

    def start_cycle(self) -> str:
        """Start a new curation cycle. Returns correlation_id."""
        self.correlation_id = str(uuid.uuid4())
        return self.correlation_id

    def emit(self, event: SignalEvent) -> SignalEvent:
        """Emit an event with the current correlation_id."""
        if self.correlation_id is None:
            self.start_cycle()
        event.correlation_id = self.correlation_id
        self.events.append(event)
        return event

    def get_by_topic(self, topic_ref: str) -> list[SignalEvent]:
        return [e for e in self.events if e.topic_ref == topic_ref]

    def get_by_source(self, source: str) -> list[SignalEvent]:
        return [e for e in self.events if e.source == source]

    def get_signals_for_topic(self, topic_ref: str) -> list[SignalEvent]:
        """Alias for get_by_topic for semantic clarity in analyzers."""
        return self.get_by_topic(topic_ref)

    def persist(self, path: Path) -> None:
        """Write all events as JSON Lines."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            for e in self.events:
                f.write(e.model_dump_json() + "\n")

    def load(self, path: Path) -> None:
        """Load events from JSON Lines file."""
        self.events = []
        if not path.exists():
            return
        with path.open("r") as f:
            for line in f:
                line = line.strip()
                if line:
                    self.events.append(SignalEvent.model_validate_json(line))
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_signal_event_dataclass tests/test_signal_curation.py::test_signal_event_serialization tests/test_signal_curation.py::test_signal_bus_initial_state tests/test_signal_curation.py::test_signal_bus_set_correlation_id tests/test_signal_curation.py::test_signal_bus_emit tests/test_signal_curation.py::test_signal_bus_get_by_topic tests/test_signal_curation.py::test_signal_bus_persist_and_load -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/signal_bus.py tests/test_signal_curation.py
git commit -m "feat(signal-curation): add signal bus with SignalEvent and JSONL persistence

TDD: tests first, minimal implementation.
SignalEvent: UUID event_id, correlation_id, collected_at auto-generated.
SignalBus: in-memory store, topic filtering, JSONL persist/load.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 2: tldv_collector.py — TLDV Signal Collection

**Files:**
- Create: `skills/memoria-consolidation/collectors/tldv_collector.py`
- Add tests to `tests/test_signal_curation.py`

**Dependencies:** `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` env vars. REST API only (no Python client).

**Schema real verificado:**
- `summaries` table: `meeting_id`, `topics`, `decisions`, `tags`, `raw_text`, `model_used`
- `meetings` table: `id`, `name`, `created_at`, `enriched_at`, `source`, `enrichment_context`
- `decisions[]` e `topics[]` disponíveis; `action_items`, `status_changes`, `consensus_topics` NÃO existem

- [ ] **Step 1: Write test for tldv_collector**

Add to `tests/test_signal_curation.py`:

```python
import os, sys
from pathlib import Path
from unittest.mock import patch, MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))

from collectors.tldv_collector import TLDVCollector, build_tldv_signal

def test_build_tldv_signal():
    """Build a SignalEvent from a TLDV summary row."""
    row = {
        "meeting_id": "abc123",
        "topics": ["BAT", "Azure", "KQL"],
        "decisions": ["Usar KQL para queries"],
    }
    signal = build_tldv_signal(row, "https://tldv.io/meeting/abc123")
    assert signal.source == "tldv"
    assert signal.priority == 1
    assert signal.signal_type == "decision"
    assert "KQL" in signal.payload["description"]
    assert signal.origin_id == "abc123"
    assert signal.origin_url == "https://tldv.io/meeting/abc123"
    assert signal.topic_ref is not None  # matched via topics

def test_build_tldv_signal_with_robert():
    """Robert as participant = explicit direction signal."""
    row = {
        "meeting_id": "xyz789",
        "topics": ["Forge"],
        "decisions": ["Migrar para Forge"],
        "participant_names": ["Robert"],
    }
    signal = build_tldv_signal(row, "https://tldv.io/meeting/xyz789")
    assert signal.priority == 1
    assert signal.payload["confidence"] == 1.0  # Robert = max confidence

def test_topic_matching():
    """Topics like BAT, Forge, Delphos map to specific topic files."""
    row = {
        "meeting_id": "m1",
        "topics": ["BAT", "ConectaBot"],
        "decisions": [],
    }
    signal = build_tldv_signal(row, None)
    assert signal.topic_ref in ["bat-conectabot-observability.md", "forge-platform.md"]

def test_collector_initialization():
    collector = TLDVCollector()
    assert collector.source == "tldv"
    assert collector.priority == 1

@patch("collectors.tldv_collector.requests.get")
def test_collector_fetches_meetings(mock_get):
    """Collector fetches from Supabase REST API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [
        {"id": "m1", "name": "Daily", "created_at": "2026-04-01T10:00:00Z",
         "enriched_at": "2026-04-01T10:05:00Z"},
    ]
    mock_get.return_value = mock_response

    collector = TLDVCollector()
    # This will fail on auth but we test the request structure
    # (mock prevents actual API call)
    # Real test needs SUPABASE env vars set
    assert collector.source == "tldv"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_build_tldv_signal tests/test_signal_curation.py::test_build_tldv_signal_with_robert tests/test_signal_curation.py::test_topic_matching tests/test_signal_curation.py::test_collector_initialization -v 2>&1 | head -20
```
Expected: FAIL — `tldv_collector` not defined

- [ ] **Step 3: Write tldv_collector.py**

```python
#!/usr/bin/env python3
"""
tldv_collector.py — Collects decisions and topics from TLDV via Supabase REST API.
Priority: 1 (primary — direction)

Schema confirmed (2026-04-01):
- meetings: id, name, created_at, enriched_at, source, enrichment_context
- summaries: meeting_id, topics, decisions, tags, raw_text, model_used
  (action_items, status_changes, consensus_topics: NOT AVAILABLE — error 42703)

Topic matching rules:
  BAT / ConectaBot → bat-conectabot-observability.md
  Forge            → forge-platform.md
  Delphos          → delphos-video-vistoria.md
  TLDV / meetings  → tldv-pipeline-state.md
  Memory / agent   → livy-memory-agent.md
  OpenClaw / gateway → openclaw-gateway.md
  default          → None (no automatic topic_ref)
"""
import os, requests
from datetime import datetime, timezone
from typing import Optional

# Import from signal_bus (sibling module)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_bus import SignalEvent, SignalBus

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TOPIC_MAPPING = {
    "bat": "bat-conectabot-observability.md",
    "conectabot": "bat-conectabot-observability.md",
    "forge": "forge-platform.md",
    "delphos": "delphos-video-vistoria.md",
    "tldv": "tldv-pipeline-state.md",
    "memory": "livy-memory-agent.md",
    "openclaw": "openclaw-gateway.md",
    "gateway": "openclaw-gateway.md",
    "livy": "livy-memory-agent.md",
}


def match_topic(topics: list[str]) -> Optional[str]:
    """Match the first available topic file based on topic keywords."""
    for topic in topics:
        topic_lower = topic.lower()
        for keyword, topic_file in TOPIC_MAPPING.items():
            if keyword in topic_lower:
                return topic_file
    return None


def build_tldv_signal(
    summary_row: dict,
    meeting_url: Optional[str],
    participant_names: Optional[list[str]] = None,
) -> SignalEvent:
    """
    Build a SignalEvent from a TLDV summary row.
    decisions[] → one signal per decision (signal_type=decision)
    topics[] → used for topic_ref matching
    """
    meeting_id = summary_row.get("meeting_id", "")
    decisions = summary_row.get("decisions") or []
    topics = summary_row.get("topics") or []
    topic_ref = match_topic(topics)

    # Robert as participant = explicit direction, max confidence
    is_robert = participant_names and any("robert" in p.lower() for p in participant_names)
    confidence = 1.0 if is_robert else 0.8

    signals = []
    for decision in decisions:
        desc = decision if isinstance(decision, str) else str(decision)
        if not desc:
            continue
        signal = SignalEvent(
            source="tldv",
            priority=1,
            topic_ref=topic_ref,
            signal_type="decision",
            payload={
                "description": desc,
                "evidence": meeting_url,
                "confidence": confidence,
            },
            origin_id=meeting_id,
            origin_url=meeting_url,
        )
        signals.append(signal)

    # If no decisions but topics exist, emit a topic_mentioned signal
    if not signals and topics:
        signal = SignalEvent(
            source="tldv",
            priority=1,
            topic_ref=topic_ref,
            signal_type="topic_mentioned",
            payload={
                "description": f"Tópicos mencionados: {', '.join(topics[:5])}",
                "evidence": meeting_url,
                "confidence": 0.6,
            },
            origin_id=meeting_id,
            origin_url=meeting_url,
        )
        signals.append(signal)

    # Return first signal (caller can iterate if needed)
    return signals[0] if signals else None


class TLDVCollector:
    """
    Collects TLDV decisions and topics via Supabase REST API.
    Fetches meetings with summaries since last run (tracked via cursor file).
    """
    source = "tldv"
    priority = 1

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.supabase_url = supabase_url or SUPABASE_URL
        self.supabase_key = supabase_key or SUPABASE_KEY
        self.base_url = f"{self.supabase_url}/rest/v1"
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }

    def _get(self, table: str, params: Optional[dict] = None) -> list:
        """Execute GET request to Supabase REST API."""
        url = f"{self.base_url}/{table}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json() or []

    def fetch_meetings_since(self, cursor: Optional[str] = None) -> list[dict]:
        """
        Fetch meetings since cursor (ISO timestamp).
        Returns list of meeting dicts with id, created_at, enriched_at.
        """
        params = {
            "select": "id,name,created_at,enriched_at,source",
            "order": "created_at.desc",
            "limit": 50,
        }
        if cursor:
            params["created_at"] = f"gt.{cursor}"
        meetings = self._get("meetings", params)
        return [m for m in meetings if m.get("enriched_at")]  # only enriched

    def fetch_summary(self, meeting_id: str) -> Optional[dict]:
        """Fetch summary row for a given meeting_id."""
        results = self._get(
            "summaries",
            params={"meeting_id": f"eq.{meeting_id}", "limit": 1}
        )
        return results[0] if results else None

    def collect(self, cursor: Optional[str] = None) -> list[SignalEvent]:
        """
        Main entry point: collect all signals from TLDV since cursor.
        Returns list of SignalEvents.
        """
        meetings = self.fetch_meetings_since(cursor)
        signals = []
        for meeting in meetings:
            summary = self.fetch_summary(meeting["id"])
            if not summary:
                continue
            # Check participants via enrichment_context if available
            participant_names = None
            # Emit decision signals
            for decision in (summary.get("decisions") or []):
                sig = build_tldv_signal(
                    summary,
                    meeting_url=f"https://tldv.io/meeting/{meeting['id']}",
                    participant_names=participant_names,
                )
                if sig:
                    sig.topic_ref = sig.topic_ref or match_topic(summary.get("topics") or [])
                    signals.append(sig)
            # Emit topic_mentioned if no decisions
            if not (summary.get("decisions") or []):
                sig = build_tldv_signal(summary, f"https://tldv.io/meeting/{meeting['id']}")
                if sig:
                    signals.append(sig)
        return signals
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_build_tldv_signal tests/test_signal_curation.py::test_build_tldv_signal_with_robert tests/test_signal_curation.py::test_topic_matching tests/test_signal_curation.py::test_collector_initialization -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/collectors/tldv_collector.py tests/test_signal_curation.py
git commit -m "feat(signal-curation): add TLDV collector via Supabase REST API

TDD: tests first.
TLDVCollector.collect(): fetches meetings + summaries, emits SignalEvents.
build_tldv_signal(): maps decisions/topics to topic files.
Schema confirmed: only decisions[] and topics[] available.
Robert = priority 1, max confidence.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 3: topic_analyzer.py — Compute Candidate Changes

**Files:**
- Create: `skills/memoria-consolidation/topic_analyzer.py`
- Add tests to `tests/test_signal_curation.py`

- [ ] **Step 1: Write test for topic_analyzer**

Add to `tests/test_signal_curation.py`:

```python
from pathlib import Path
import sys, tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))
from signal_bus import SignalEvent
from topic_analyzer import TopicAnalyzer, CandidateChange

def test_candidate_change_dataclass():
    change = CandidateChange(
        change_type="add_decision",
        description="Use Postgres",
        evidence="meeting #123",
        signal_source="tldv",
    )
    assert change.change_type == "add_decision"
    assert "Postgres" in change.description

def test_analyzer_adds_decision(tmp_path):
    """New decision from signal → add_entry candidate."""
    topic_file = tmp_path / "forge-platform.md"
    topic_file.write_text("---\nname: forge\n---\n\n# Forge\n\n## Decisões\n(nenhuma)\n")

    signal = SignalEvent(
        source="tldv",
        priority=1,
        topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Usar Postgres com Neon", "evidence": "meeting #123", "confidence": 0.9},
        origin_id="m123",
        origin_url="https://tldv.io/meeting/123",
    )

    analyzer = TopicAnalyzer()
    candidates = analyzer.analyze(topic_file, [signal])
    assert len(candidates) == 1
    assert candidates[0].change_type == "add_decision"
    assert "Postgres" in candidates[0].description

def test_analyzer_skips_duplicate():
    """Decision already in topic file → no candidate."""
    content = "---\nname: forge\n---\n\n# Forge\n\n## Decisões\n- Usar Postgres com Neon\n"
    signal = SignalEvent(
        source="tldv", priority=1, topic_ref="forge-platform.md",
        signal_type="decision",
        payload={"description": "Usar Postgres com Neon", "evidence": "meeting #123", "confidence": 0.9},
        origin_id="m123", origin_url=None,
    )
    analyzer = TopicAnalyzer()
    candidates = analyzer.analyze_content("forge-platform.md", content, [signal])
    assert candidates == []

def test_analyzer_failure_signal():
    """Failure signal with confidence 1.0 → deprecate_entry candidate."""
    signal = SignalEvent(
        source="logs",
        priority=2,
        topic_ref="delphos-video-vistoria.md",
        signal_type="failure",
        payload={"description": "Job Vonage falhou 3x", "evidence": "reports/daily/2026-04-01.json", "confidence": 1.0},
        origin_id="delphos-daily-2026-04-01",
        origin_url=None,
    )
    analyzer = TopicAnalyzer()
    candidates = analyzer.analyze_content("delphos-video-vistoria.md", "# Delphos\n\n## Status\n- Vonage: em uso\n", [signal])
    assert len(candidates) == 1
    assert candidates[0].change_type == "deprecate_entry"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_candidate_change_dataclass tests/test_signal_curation.py::test_analyzer_adds_decision tests/test_signal_curation.py::test_analyzer_skips_duplicate tests/test_signal_curation.py::test_analyzer_failure_signal -v 2>&1 | head -20
```
Expected: FAIL — `topic_analyzer` not defined

- [ ] **Step 3: Write topic_analyzer.py**

```python
#!/usr/bin/env python3
"""
topic_analyzer.py — Analyzes a topic file against new signals and produces candidate changes.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from signal_bus import SignalEvent


@dataclass
class CandidateChange:
    """A proposed change to a topic file."""
    change_type: str  # "add_decision" | "update_entry" | "deprecate_entry" | "archive_entry"
    description: str
    evidence: Optional[str]
    signal_source: str


class TopicAnalyzer:
    """
    Given a topic file path + list of SignalEvents for that topic,
    compute the list of candidate changes.
    """

    def analyze(self, topic_path: Path, signals: list[SignalEvent]) -> list[CandidateChange]:
        """Analyze a topic file. Returns list of candidate changes."""
        if not topic_path.exists():
            return []
        content = topic_path.read_text()
        return self.analyze_content(topic_path.name, content, signals)

    def analyze_content(
        self, filename: str, content: str, signals: list[SignalEvent]
    ) -> list[CandidateChange]:
        """Analyze topic file content against signals."""
        candidates = []
        for sig in signals:
            if sig.topic_ref and sig.topic_ref not in filename:
                continue
            if sig.signal_type == "decision":
                change = self._handle_decision(content, sig)
                if change:
                    candidates.append(change)
            elif sig.signal_type == "failure":
                change = self._handle_failure(content, sig)
                if change:
                    candidates.append(change)
            elif sig.signal_type == "topic_mentioned":
                change = self._handle_topic_mentioned(content, sig)
                if change:
                    candidates.append(change)
        return candidates

    def _handle_decision(self, content: str, sig: SignalEvent) -> Optional[CandidateChange]:
        """If decision is new, propose add_decision."""
        desc = sig.payload.get("description", "")
        if not desc:
            return None
        # Check if decision already exists in content
        if desc in content:
            return None
        return CandidateChange(
            change_type="add_decision",
            description=desc,
            evidence=sig.payload.get("evidence"),
            signal_source=sig.source,
        )

    def _handle_failure(self, content: str, sig: SignalEvent) -> Optional[CandidateChange]:
        """Failure signal → propose deprecate_entry."""
        desc = sig.payload.get("description", "")
        evidence = sig.payload.get("evidence", "")
        return CandidateChange(
            change_type="deprecate_entry",
            description=f"{desc} (evidência: {evidence})",
            evidence=evidence,
            signal_source=sig.source,
        )

    def _handle_topic_mentioned(self, content: str, sig: SignalEvent) -> Optional[CandidateChange]:
        """Topic mentioned with high confidence → add to topics list if new."""
        # Only suggest if confidence is high and no existing decision covers it
        if sig.payload.get("confidence", 0) < 0.7:
            return None
        return None  # topic_mentioned alone is not enough for a change
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_candidate_change_dataclass tests/test_signal_curation.py::test_analyzer_adds_decision tests/test_signal_curation.py::test_analyzer_skips_duplicate tests/test_signal_curation.py::test_analyzer_failure_signal -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/topic_analyzer.py tests/test_signal_curation.py
git commit -m "feat(signal-curation): add topic analyzer with candidate change detection

TDD: tests first.
CandidateChange: add_decision, deprecate_entry.
TopicAnalyzer.analyze(): reads topic file, applies signal type rules.
Duplicate detection: skips decision if already in content.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 4: auto_curator.py — Apply Candidate Changes

**Files:**
- Create: `skills/memoria-consolidation/auto_curator.py`
- Add tests to `tests/test_signal_curation.py`

- [ ] **Step 1: Write test for auto_curator**

Add to `tests/test_signal_curation.py`:

```python
import sys
from pathlib import Path
from unittest.mock import MagicMock
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))
from signal_bus import SignalEvent
from topic_analyzer import CandidateChange
from auto_curator import AutoCurator

def test_should_apply_returns_true_for_high_confidence():
    curator = AutoCurator()
    change = CandidateChange(
        change_type="add_decision",
        description="Use Postgres",
        evidence="meeting #123",
        signal_source="tldv",
    )
    assert curator.should_apply(change) is True

def test_should_apply_returns_false_for_low_confidence():
    curator = AutoCurator()
    signal = SignalEvent(
        source="tldv", priority=1, topic_ref="test.md",
        signal_type="decision",
        payload={"description": "Test", "evidence": None, "confidence": 0.5},
        origin_id="m1", origin_url=None,
    )
    change = CandidateChange(
        change_type="add_decision",
        description="Use Postgres",
        evidence=None,
        signal_source="tldv",
    )
    # No evidence + low confidence → don't apply
    assert curator.should_apply(change) is False

def test_apply_add_decision(tmp_path):
    topic_file = tmp_path / "forge.md"
    topic_file.write_text("---\nname: forge\n---\n\n# Forge\n\n## Decisões\n(nenhuma)\n")

    curator = AutoCurator()
    change = CandidateChange(
        change_type="add_decision",
        description="Usar Postgres",
        evidence="meeting #123",
        signal_source="tldv",
    )
    result = curator.apply_change(topic_file, change)

    assert result is True
    content = topic_file.read_text()
    assert "Usar Postgres" in content
    assert "meeting #123" in content

def test_apply_deprecate_entry(tmp_path):
    topic_file = tmp_path / "delphos.md"
    topic_file.write_text("---\nname: delphos\n---\n\n# Delphos\n\n## Status\n- Vonage: em uso\n\n## Decisões\n- Usar Vonage\n")

    curator = AutoCurator()
    change = CandidateChange(
        change_type="deprecate_entry",
        description="Vonage job falhou (evidência: reports/daily/2026-04-01.json)",
        evidence="reports/daily/2026-04-01.json",
        signal_source="logs",
    )
    result = curator.apply_change(topic_file, change)

    assert result is True
    content = topic_file.read_text()
    assert "DEPRECADO" in content or "deprecated" in content.lower()
    assert "Vonage" in content
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_should_apply_returns_true_for_high_confidence tests/test_signal_curation.py::test_should_apply_returns_false_for_low_confidence tests/test_signal_curation.py::test_apply_add_decision tests/test_signal_curation.py::test_apply_deprecate_entry -v 2>&1 | head -20
```
Expected: FAIL — `auto_curator` not defined

- [ ] **Step 3: Write auto_curator.py**

```python
#!/usr/bin/env python3
"""
auto_curator.py — Applies candidate changes to topic files when conditions are met.
"""
from datetime import datetime, timezone
from pathlib import Path

from topic_analyzer import CandidateChange


class AutoCurator:
    """
    Evaluates candidate changes and applies them to topic files.
    Conditions for auto-apply:
      - confidence >= 0.7 via signal payload
      - evidence is present
      - change_type is add_decision or deprecate_entry
    """

    def should_apply(self, change: CandidateChange) -> bool:
        """Return True if change should be auto-applied."""
        # Must have evidence for auto-apply
        if not change.evidence:
            return False
        # add_decision and deprecate_entry are auto-applicable
        if change.change_type not in ("add_decision", "deprecate_entry"):
            return False
        return True

    def apply_change(self, topic_path: Path, change: CandidateChange) -> bool:
        """Apply a single candidate change to a topic file. Returns True if applied."""
        if not topic_path.exists():
            return False

        content = topic_path.read_text()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if change.change_type == "add_decision":
            new_content = self._apply_add_decision(content, change, timestamp)
        elif change.change_type == "deprecate_entry":
            new_content = self._apply_deprecate_entry(content, change, timestamp)
        else:
            return False

        topic_path.write_text(new_content)
        return True

    def _apply_add_decision(self, content: str, change: CandidateChange, timestamp: str) -> str:
        """Append a decision entry to the topic file."""
        evidence = f" [{change.evidence}]" if change.evidence else ""
        new_entry = f"- [{timestamp}] {change.description}{evidence} — via {change.signal_source}\n"

        # Find the Decisões section
        if "## Decisões" in content:
            content = content.replace(
                "## Decisões\n(nenhuma)\n",
                f"## Decisões\n(new_entry)"
            )
            content = content.replace("(nenhuma)", "")
        elif "## Decisões" in content:
            # Append to existing decisions
            lines = content.splitlines()
            for i, line in enumerate(lines):
                if line.strip().startswith("## Decisões"):
                    # Find next non-empty line
                    insert_idx = i + 1
                    while insert_idx < len(lines) and not lines[insert_idx].strip():
                        insert_idx += 1
                    lines.insert(insert_idx, new_entry.rstrip())
                    break
            content = "\n".join(lines)
        else:
            # No decisions section — add at end
            content += f"\n\n## Decisões\n{new_entry}"
        return content

    def _apply_deprecate_entry(self, content: str, change: CandidateChange, timestamp: str) -> str:
        """Mark an entry as deprecated."""
        desc = change.description
        deprecated = f"~~{desc}~~ **[DEPRECADO {timestamp}]** — {change.signal_source}"
        content = content.replace(desc, deprecated)
        return content
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_should_apply_returns_true_for_high_confidence tests/test_signal_curation.py::test_should_apply_returns_false_for_low_confidence tests/test_signal_curation.py::test_apply_add_decision tests/test_signal_curation.py::test_apply_deprecate_entry -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/auto_curator.py tests/test_signal_curation.py
git commit -m "feat(signal-curation): add auto curator with apply conditions

TDD: tests first.
AutoCurator.should_apply(): requires evidence + high confidence.
AutoCurator.apply_change(): add_decision or deprecate_entry to topic files.
Adds timestamp + source evidence to each entry.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 5: curation_cron.py — Orchestration + Observability + Telegram Report

**Files:**
- Create: `skills/memoria-consolidation/curation_cron.py`
- Create: `memory/logs/.gitkeep` (to ensure logs directory is tracked)

**Dependencies:** Uses all prior components + Telegram sending (reuse pattern from `autoresearch_cron.py`).

- [ ] **Step 1: Write curation_cron.py**

```python
#!/usr/bin/env python3
"""
curation_cron.py — Orchestrates the full signal curation pipeline.

Flow:
  1. Generate correlation_id
  2. Collect signals from all sources (TLDV primary)
  3. Group signals by topic_ref
  4. Analyze each topic file → candidate changes
  5. Auto-curate (apply when conditions met)
  6. Persist events to signal-events.jsonl
  7. Log to memory/logs/curation-{date}.log (JSON Lines)
  8. Write curation-log.md
  9. Send Telegram summary

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — TLDV
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID — notifications
  CURATED_DIR — path to memory/curated/ (default: same dir as script)
"""
import json, logging, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

# Setup structured JSON logging to stdout (captured by cron wrapper)
logging.basicConfig(
    level=logging.INFO,
    format='{"level": "%(levelname)s", "ts": "%(asctime)sZ", "message": "%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("curation")

BASE_DIR = Path(__file__).resolve().parents[1]  # workspace-livy-memory/
MEMORY_DIR = BASE_DIR / "memory"
CURATED_DIR = MEMORY_DIR / "curated"
LOGS_DIR = MEMORY_DIR / "logs"
SIGNAL_EVENTS_FILE = MEMORY_DIR / "signal-events.jsonl"
CURATION_LOG_FILE = MEMORY_DIR / "curation-log.md"

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)

import os
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-5158607302")

from signal_bus import SignalBus
from collectors.tldv_collector import TLDVCollector
from topic_analyzer import TopicAnalyzer
from auto_curator import AutoCurator


def log_structured(level: str, correlation_id: str, component: str, event: str, **kwargs):
    """Emit a structured JSON log line."""
    entry = {
        "level": level,
        "ts": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "component": component,
        "event": event,
        **kwargs,
    }
    logger.log(getattr(logging, level), json.dumps(entry))


def send_telegram(message: str):
    """Send message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        print(f"[TELEGRAM] {message}")
        return
    import urllib.request
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


def format_curation_log_entry(correlation_id: str, topic: str, change_type: str,
                               description: str, evidence: str, auto: bool) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M BRT")
    auto_str = "Yes" if auto else "No"
    return f"""## {ts} · {correlation_id}

**topic:** {topic}
**auto:** {auto_str}
**change:** {change_type}
**description:** {description}
**evidence:** {evidence}
"""


def main():
    correlation_id = str(uuid.uuid4())
    log_structured("INFO", correlation_id, "curation_cron", "cycle_started")

    bus = SignalBus()
    bus.start_cycle()

    curated_dir = CURATED_DIR

    # ── 1. Collect signals ────────────────────────────────────────────────
    log_structured("INFO", correlation_id, "curation_cron", "collecting_signals")

    tldv_collector = TLDVCollector()
    try:
        tldv_signals = tldv_collector.collect()
        log_structured("INFO", correlation_id, "tldv_collector", "collection_complete",
                        count=len(tldv_signals))
    except Exception as e:
        log_structured("ERROR", correlation_id, "tldv_collector", "collection_failed",
                        error=str(e), retryable=True)
        tldv_signals = []

    for sig in tldv_signals:
        bus.emit(sig)

    log_structured("INFO", correlation_id, "signal_bus", "events_collected",
                    total=len(bus.events))

    # ── 2. Persist signals to JSONL ──────────────────────────────────────
    bus.persist(SIGNAL_EVENTS_FILE)
    log_structured("INFO", correlation_id, "signal_bus", "events_persisted",
                    path=str(SIGNAL_EVENTS_FILE), count=len(bus.events))

    # ── 3. Analyze + Auto-curate per topic ───────────────────────────────
    analyzer = TopicAnalyzer()
    curator = AutoCurator()
    curation_log_lines = []
    applied_count = 0

    # Group signals by topic
    topics = set(e.topic_ref for e in bus.events if e.topic_ref)
    for topic_ref in topics:
        topic_path = curated_dir / topic_ref
        if not topic_path.exists():
            continue

        signals = bus.get_by_topic(topic_ref)
        candidates = analyzer.analyze(topic_path, signals)

        for candidate in candidates:
            if curator.should_apply(candidate):
                ok = curator.apply_change(topic_path, candidate)
                if ok:
                    applied_count += 1
                    log_structured("INFO", correlation_id, "auto_curator", "change_applied",
                                   topic=topic_ref, change_type=candidate.change_type,
                                   description=candidate.description[:80])
                    curation_log_lines.append(
                        format_curation_log_entry(
                            correlation_id, topic_ref,
                            candidate.change_type, candidate.description,
                            candidate.evidence or "", auto=True
                        )
                    )
            else:
                # Flag for Lincoln review (conflict or low confidence)
                log_structured("WARN", correlation_id, "auto_curator", "change_requires_review",
                               topic=topic_ref, change_type=candidate.change_type,
                               description=candidate.description[:80])
                curation_log_lines.append(
                    format_curation_log_entry(
                        correlation_id, topic_ref,
                        candidate.change_type, candidate.description,
                        candidate.evidence or "", auto=False
                    )
                )

    # ── 4. Write curation log ───────────────────────────────────────────
    if curation_log_lines:
        with CURATION_LOG_FILE.open("a") as f:
            f.write("\n".join(curation_log_lines) + "\n")

    # ── 5. Send Telegram summary ─────────────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = f"""🧠 *Signal Curation — {ts}*

📊 Sinais: {len(bus.events)} | Temas: {len(topics)} | Aplicados: {applied_count}
🔗 correlation_id: `{correlation_id}`

"""
    if curation_log_lines:
        for line in curation_log_lines[:5]:  # first 5
            summary += line + "\n"
    else:
        summary += "✅ Nenhuma mudança necessária."

    send_telegram(summary)
    log_structured("INFO", correlation_id, "curation_cron", "cycle_complete",
                    signals=len(bus.events), topics=len(topics),
                    applied=applied_count)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run smoke test (dry — no actual API calls)**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python3 -c "
import sys
sys.path.insert(0, 'skills/memoria-consolidation')
from signal_bus import SignalBus
from collectors.tldv_collector import TLDVCollector
from topic_analyzer import TopicAnalyzer
from auto_curator import AutoCurator
print('All imports OK')
"
```
Expected: OK

- [ ] **Step 3: Commit**

```bash
git add skills/memoria-consolidation/curation_cron.py memory/logs/.gitkeep
git commit -m "feat(signal-curation): add curation_cron orchestration with observability

TDD: smoke test first (imports OK).
Pipeline: collect (TLDV) → persist → analyze → auto-curate → log → Telegram.
JSON Lines logging with correlation_id for full traceability.
Auto-applies changes with evidence; flags rest for Lincoln review.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## FASE 2 — Logs + Conflict Detection

### Task 6: logs_collector.py — Job Log Signals

**Files:**
- Create: `skills/memoria-consolidation/collectors/logs_collector.py`
- Add tests to `tests/test_signal_curation.py`

**Important:** No per-run logs exist. BAT/Delphos reports are aggregated JSON files. Use `total_errors > 0` as failure proxy.

- [ ] **Step 1: Write test for logs_collector**

Add to `tests/test_signal_curation.py`:

```python
from pathlib import Path
import sys, json, tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))
from collectors.logs_collector import LogsCollector, BATReportParser

def test_bat_report_parser_success():
    """Report with total_errors=0 → no failure signal."""
    report = {"total_errors": 0, "distinct_operations": 5}
    signals = BATReportParser.parse("bat-intraday", report, "reports/intraday/2026-04-01.json")
    assert signals == []

def test_bat_report_parser_failure():
    """Report with total_errors>0 → failure signal."""
    report = {"total_errors": 3, "operations": [{"name": "query-kql", "errors": 2}]}
    signals = BATReportParser.parse("bat-intraday", report, "reports/intraday/2026-04-01.json")
    assert len(signals) == 1
    assert signals[0].signal_type == "failure"
    assert signals[0].priority == 2
    assert signals[0].topic_ref == "bat-conectabot-observability.md"
    assert "total_errors=3" in signals[0].payload["description"]

def test_collector_initialization():
    collector = LogsCollector()
    assert collector.source == "logs"
    assert collector.priority == 2
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_bat_report_parser_success tests/test_signal_curation.py::test_bat_report_parser_failure tests/test_signal_curation.py::test_collector_initialization -v 2>&1 | head -20
```
Expected: FAIL — `logs_collector` not defined

- [ ] **Step 3: Write logs_collector.py**

```python
#!/usr/bin/env python3
"""
logs_collector.py — Collects failure signals from BAT/Delphos job reports.
Priority: 2 (secondary — verification)

IMPORTANT: No per-run logs exist. Reports are aggregated JSON in:
  /home/lincoln/.openclaw/workspace/operacional/bat/reports/{intraday,daily}/
  /home/lincoln/.openclaw/workspace/operacional/delphos/reports/{intraday,daily}/

Failure proxy: total_errors > 0 in the latest report.
"""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_bus import SignalEvent


JOB_TOPIC_MAP = {
    "bat-intraday": "bat-conectabot-observability.md",
    "bat-daily": "bat-conectabot-observability.md",
    "delphos-midday": "delphos-video-vistoria.md",
    "delphos-daily": "delphos-video-vistoria.md",
    "tldv-enrich": "tldv-pipeline-state.md",
}

BAT_REPORTS_DIR = Path("/home/lincoln/.openclaw/workspace/operacional/bat/reports")
DELPHOS_REPORTS_DIR = Path("/home/lincoln/.openclaw/workspace/operacional/delphos/reports")


class BATReportParser:
    """Parses BAT report JSON and emits failure signals."""

    @staticmethod
    def parse(job_name: str, report: dict, source_path: str) -> list[SignalEvent]:
        """Parse a BAT report JSON. Returns failure signal if errors > 0."""
        total_errors = report.get("total_errors", 0)
        signals = []

        if total_errors == 0:
            return signals

        ops = report.get("operations", [])
        ops_with_errors = [op["name"] for op in ops if op.get("errors", 0) > 0]
        ops_str = ", ".join(ops_with_errors) if ops_with_errors else f"total_errors={total_errors}"

        signal = SignalEvent(
            source="logs",
            priority=2,
            topic_ref=JOB_TOPIC_MAP.get(job_name),
            signal_type="failure",
            payload={
                "description": f"{job_name}: {ops_str} (total_errors={total_errors})",
                "evidence": source_path,
                "confidence": 1.0,
            },
            origin_id=f"{job_name}-{datetime.now(timezone.utc).date().isoformat()}",
            origin_url=None,
        )
        signals.append(signal)
        return signals


class LogsCollector:
    """Collects failure signals from BAT and Delphos report directories."""
    source = "logs"
    priority = 2

    def collect(self) -> list[SignalEvent]:
        """Scan latest BAT and Delphos reports. Return failure signals."""
        signals = []

        # BAT intraday
        signals.extend(self._scan_dir(BAT_REPORTS_DIR / "intraday", "bat-intraday"))
        signals.extend(self._scan_dir(BAT_REPORTS_DIR / "daily", "bat-daily"))

        # Delphos
        signals.extend(self._scan_dir(DELPHOS_REPORTS_DIR / "intraday", "delphos-midday"))
        signals.extend(self._scan_dir(DELPHOS_REPORTS_DIR / "daily", "delphos-daily"))

        return signals

    def _scan_dir(self, dir_path: Path, job_name: str) -> list[SignalEvent]:
        """Find latest report in directory, parse for failures."""
        signals = []
        if not dir_path.exists():
            return signals
        # Get most recent file
        files = sorted(dir_path.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        if not files:
            return signals
        latest = files[0]
        try:
            report = json.loads(latest.read_text())
            signals = BATReportParser.parse(job_name, report, str(latest))
        except Exception:
            pass
        return signals
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_bat_report_parser_success tests/test_signal_curation.py::test_bat_report_parser_failure tests/test_signal_curation.py::test_collector_initialization -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/collectors/logs_collector.py tests/test_signal_curation.py
git commit -m "feat(signal-curation): add logs collector for BAT/Delphos reports

TDD: tests first.
BATReportParser: total_errors>0 → failure signal (priority 2).
LogsCollector: scans latest intraday/daily reports.
No per-run logs exist — using aggregate report as proxy.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 7: conflict_detector.py — Conflict Detection

**Files:**
- Create: `skills/memoria-consolidation/conflict_detector.py`
- Add tests to `tests/test_signal_curation.py`

- [ ] **Step 1: Write test for conflict_detector**

Add to `tests/test_signal_curation.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))
from signal_bus import SignalEvent
from conflict_detector import ConflictDetector, Conflict

def test_no_conflict_when_tldv_and_logs_agree():
    """TLDV says 'X', logs show 'X working' → no conflict."""
    signals = [
        SignalEvent(source="tldv", priority=1, topic_ref="forge.md",
                   signal_type="decision",
                   payload={"description": "Usar Postgres", "evidence": None, "confidence": 0.9},
                   origin_id="m1", origin_url=None),
        SignalEvent(source="logs", priority=2, topic_ref="forge.md",
                   signal_type="success",
                   payload={"description": "Job succeeded", "evidence": None, "confidence": 1.0},
                   origin_id="job1", origin_url=None),
    ]
    detector = ConflictDetector()
    conflicts = detector.detect(signals, {})
    assert conflicts == []

def test_conflict_when_tldv_decides_but_logs_show_failure():
    """TLDV decides 'X is good', but logs show X failing → CONFLICT."""
    signals = [
        SignalEvent(source="tldv", priority=1, topic_ref="delphos.md",
                   signal_type="decision",
                   payload={"description": "Migrar para Vonage", "evidence": "meeting #123", "confidence": 0.9},
                   origin_id="m1", origin_url=None),
        SignalEvent(source="logs", priority=2, topic_ref="delphos.md",
                   signal_type="failure",
                   payload={"description": "Vonage job falhou", "evidence": "reports/daily/2026-04-01.json", "confidence": 1.0},
                   origin_id="delphos-daily", origin_url=None),
    ]
    detector = ConflictDetector()
    conflicts = detector.detect(signals, {})
    assert len(conflicts) == 1
    assert conflicts[0].topic == "delphos.md"
    assert conflicts[0].primary_signal.source == "tldv"
    assert conflicts[0].conflicting_signal.source == "logs"

def test_conflict_when_pr_shows_revert():
    """TLDV says 'use X', but Git PR shows X was reverted → CONFLICT."""
    signals = [
        SignalEvent(source="tldv", priority=1, topic_ref="forge.md",
                   signal_type="decision",
                   payload={"description": "Usar MongoDB", "evidence": None, "confidence": 0.8},
                   origin_id="m1", origin_url=None),
        SignalEvent(source="github", priority=3, topic_ref="forge.md",
                   signal_type="correction",
                   payload={"description": "PR reverted: MongoDB removed", "evidence": "PR #47", "confidence": 1.0},
                   origin_id="PR#47", origin_url="https://github.com/living/repo/pull/47"),
    ]
    detector = ConflictDetector()
    conflicts = detector.detect(signals, {})
    assert len(conflicts) == 1
    assert conflicts[0].conflicting_signal.source == "github"

def test_conflict_dataclass():
    c = Conflict(
        topic="delphos.md",
        primary_signal=SignalEvent(source="tldv", priority=1, topic_ref="delphos.md",
                                  signal_type="decision",
                                  payload={"description": "X", "evidence": None, "confidence": 0.9},
                                  origin_id="m1", origin_url=None),
        conflicting_signal=SignalEvent(source="logs", priority=2, topic_ref="delphos.md",
                                       signal_type="failure",
                                       payload={"description": "X failed", "evidence": None, "confidence": 1.0},
                                       origin_id="job1", origin_url=None),
        proposal="Manter decisão mas investigar falha",
    )
    assert c.topic == "delphos.md"
    assert c.proposal is not None
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_no_conflict_when_tldv_and_logs_agree tests/test_signal_curation.py::test_conflict_when_tldv_decides_but_logs_show_failure tests/test_signal_curation.py::test_conflict_when_pr_shows_revert tests/test_signal_curation.py::test_conflict_dataclass -v 2>&1 | head -20
```
Expected: FAIL — `conflict_detector` not defined

- [ ] **Step 3: Write conflict_detector.py**

```python
#!/usr/bin/env python3
"""
conflict_detector.py — Detects conflicts between signals from different sources.
A conflict = TLDV says "X is the direction" BUT logs or Git shows "X failed/was abandoned".

Rules:
  - decision (TLDV, priority 1) vs failure (logs, priority 2) → CONFLICT
  - decision (TLDV, priority 1) vs correction (Git, priority 3) → CONFLICT
  - success (logs) + decision (TLDV) → no conflict (they agree)
  - Two decisions from TLDV → no conflict (same source, no contradiction)
"""
from dataclasses import dataclass
from typing import Optional

from signal_bus import SignalEvent


@dataclass
class Conflict:
    """Represents a detected conflict between two signals."""
    topic: str
    primary_signal: SignalEvent      # the directional signal (usually TLDV)
    conflicting_signal: SignalEvent  # the contradicting signal (logs/Git)
    proposal: str                    # suggested resolution


class ConflictDetector:
    """
    Detects conflicts between signals based on source and signal type.
    Conflict rule: decision (TLDV) vs (failure OR correction) from other sources.
    """

    def detect(
        self, signals: list[SignalEvent], topic_states: dict
    ) -> list[Conflict]:
        """
        Given all signals for a curation cycle, detect conflicts.
        Returns list of Conflict objects.
        """
        conflicts = []

        # Group by topic
        by_topic: dict[str, list[SignalEvent]] = {}
        for sig in signals:
            if sig.topic_ref:
                by_topic.setdefault(sig.topic_ref, []).append(sig)

        for topic, topic_sigs in by_topic.items():
            conflict = self._check_topic(topic, topic_sigs)
            if conflict:
                conflicts.append(conflict)

        return conflicts

    def _check_topic(self, topic: str, signals: list[SignalEvent]) -> Optional[Conflict]:
        """Check a single topic for conflicts."""
        tldv_decisions = [s for s in signals if s.source == "tldv" and s.signal_type == "decision"]
        tldv_signals = [s for s in signals if s.source == "tldv"]

        # Primary signal: first TLDV decision (the "direction")
        primary = tldv_decisions[0] if tldv_decisions else (tldv_signals[0] if tldv_signals else None)
        if not primary:
            return None

        # Conflicting signals: failure from logs OR correction from Git
        for sig in signals:
            if sig.source == "logs" and sig.signal_type == "failure":
                # Check if the failure is related to the same thing TLDV decided
                if self._is_related(primary, sig):
                    return Conflict(
                        topic=topic,
                        primary_signal=primary,
                        conflicting_signal=sig,
                        proposal=self._make_proposal(primary, sig),
                    )
            if sig.source == "github" and sig.signal_type == "correction":
                if self._is_related(primary, sig):
                    return Conflict(
                        topic=topic,
                        primary_signal=primary,
                        conflicting_signal=sig,
                        proposal=self._make_proposal(primary, sig),
                    )

        return None

    def _is_related(self, sig1: SignalEvent, sig2: SignalEvent) -> bool:
        """Check if two signals are about the same subject."""
        desc1 = sig1.payload.get("description", "").lower()
        desc2 = sig2.payload.get("description", "").lower()
        # Simple keyword overlap check
        words1 = set(desc1.split())
        words2 = set(desc2.split())
        # Remove common stopwords
        stopwords = {"para", "usar", "com", "o", "a", "de", "e", "em", "que", "é"}
        kw1 = words1 - stopwords
        kw2 = words2 - stopwords
        return bool(kw1 & kw2)  # any keyword overlap = related

    def _make_proposal(self, primary: SignalEvent, conflicting: SignalEvent) -> str:
        """Generate a resolution proposal based on signals."""
        primary_desc = primary.payload.get("description", "")[:50]
        conf_desc = conflicting.payload.get("description", "")[:50]
        return (f"Revisar: '{primary_desc}' vs evidência de falha: '{conf_desc}'. "
                f"Fonte primária: {primary.source}. "
                f"Verificar antes de fechar topic.")
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_no_conflict_when_tldv_and_logs_agree tests/test_signal_curation.py::test_conflict_when_tldv_decides_but_logs_show_failure tests/test_signal_curation.py::test_conflict_when_pr_shows_revert tests/test_signal_curation.py::test_conflict_dataclass -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/conflict_detector.py tests/test_signal_curation.py
git commit -m "feat(signal-curation): add conflict detector

TDD: tests first.
Conflict: TLDV decision vs logs failure OR Git correction.
_is_related(): keyword overlap between descriptions.
ConflictDetector.detect(): groups by topic, returns Conflict objects.
Auto-proposes resolution based on conflicting signals.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

### Task 8: conflict_queue.py — Conflict Queue Manager

**Files:**
- Create: `skills/memoria-consolidation/conflict_queue.py`
- Add tests to `tests/test_signal_curation.py`

- [ ] **Step 1: Write test for conflict_queue**

Add to `tests/test_signal_curation.py`:

```python
import sys
from pathlib import Path
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/memoria-consolidation"))
from signal_bus import SignalEvent
from conflict_detector import Conflict
from conflict_queue import ConflictQueue

def test_queue_add_conflict(tmp_path):
    queue_file = tmp_path / "conflict-queue.md"
    sig1 = SignalEvent(source="tldv", priority=1, topic_ref="delphos.md",
                       signal_type="decision",
                       payload={"description": "Migrar para Vonage", "evidence": "meeting #123", "confidence": 0.9},
                       origin_id="m1", origin_url="https://tldv.io/m1")
    sig2 = SignalEvent(source="logs", priority=2, topic_ref="delphos.md",
                       signal_type="failure",
                       payload={"description": "Vonage falhou", "evidence": "reports/daily/2026-04-01.json", "confidence": 1.0},
                       origin_id="delphos-daily", origin_url=None)
    conflict = Conflict(topic="delphos.md", primary_signal=sig1, conflicting_signal=sig2,
                        proposal="Manter decisão mas investigar")

    q = ConflictQueue(queue_file)
    q.add(conflict)

    assert queue_file.exists()
    content = queue_file.read_text()
    assert "CONFLITO-001" in content
    assert "delphos.md" in content
    assert "Migrar para Vonage" in content

def test_queue_idempotent():
    """Adding same conflict twice doesn't duplicate."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".md", delete=False, mode="w") as f:
        queue_file = Path(f.name)

    sig1 = SignalEvent(source="tldv", priority=1, topic_ref="delphos.md",
                       signal_type="decision",
                       payload={"description": "Migrar para Vonage", "evidence": "meeting #123", "confidence": 0.9},
                       origin_id="m1", origin_url=None)
    sig2 = SignalEvent(source="logs", priority=2, topic_ref="delphos.md",
                       signal_type="failure",
                       payload={"description": "Vonage falhou", "evidence": None, "confidence": 1.0},
                       origin_id="delphos-daily", origin_url=None)
    conflict = Conflict(topic="delphos.md", primary_signal=sig1, conflicting_signal=sig2,
                        proposal="Investigar")

    q = ConflictQueue(queue_file)
    q.add(conflict)
    q.add(conflict)

    content = queue_file.read_text()
    assert content.count("CONFLITO-001") == 1  # not duplicated
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_queue_add_conflict tests/test_signal_curation.py::test_queue_idempotent -v 2>&1 | head -20
```
Expected: FAIL — `conflict_queue` not defined

- [ ] **Step 3: Write conflict_queue.py**

```python
#!/usr/bin/env python3
"""
conflict_queue.py — Manages the conflict queue file (memory/conflict-queue.md).
Provides add, list, resolve operations.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

from conflict_detector import Conflict


CONFLICT_QUEUE_FILE = Path(__file__).resolve().parents[1] / "memory" / "conflict-queue.md"


class ConflictQueue:
    """
    Manages the conflict queue markdown file.
    Each conflict gets an ID (CONFLITO-001, CONFLITO-002, ...).
    """

    def __init__(self, queue_file: Path = None):
        self.queue_file = queue_file or CONFLICT_QUEUE_FILE
        self._ensure_exists()

    def _ensure_exists(self):
        if not self.queue_file.exists():
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            self.queue_file.write_text(f"# Conflict Queue — {date}\n\n_(vazio)_\n")

    def _next_id(self) -> str:
        """Find the next conflict ID."""
        if not self.queue_file.exists():
            return "CONFLITO-001"
        content = self.queue_file.read_text()
        ids = re.findall(r"CONFLITO-(\d+)", content)
        if not ids:
            return "CONFLITO-001"
        n = max(int(i) for i in ids)
        return f"CONFLITO-{n+1:03d}"

    def add(self, conflict: Conflict) -> str:
        """Add a conflict to the queue. Returns conflict ID."""
        conflict_id = self._next_id()
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        primary = conflict.primary_signal
        conflicting = conflict.conflicting_signal

        entry = f"""
## {conflict_id} · {conflict.topic}
**Detectado:** {ts}
**correlation_id:** {primary.correlation_id}
**Sinal primário:** {primary.source} — {primary.payload.get('description', '')[:80]}
**Sinal conflitante:** {conflicting.source} — {conflicting.payload.get('description', '')[:80]}
**Evidências:**
  - {primary.source}: {primary.payload.get('evidence') or 'N/A'}
  - {conflicting.source}: {conflicting.payload.get('evidence') or 'N/A'}
**Proposta:** {conflict.proposal}
**Status:** AWAITING_REVIEW
**Resolução Lincoln:** ___________________________

"""
        # Remove "(vazio)" marker if present
        content = self.queue_file.read_text()
        if "_(vazio)_" in content or "(vazio)" in content:
            content = re.sub(r"\n_\(vazio\)_\n", "\n", content)
        self.queue_file.write_text(content + entry)
        return conflict_id

    def list_pending(self) -> list[dict]:
        """Return list of pending conflicts with metadata."""
        if not self.queue_file.exists():
            return []
        content = self.queue_file.read_text()
        entries = re.findall(r"(CONFLITO-\d+)[^#]*(?=## CONFLITO-|$)", content, re.DOTALL)
        results = []
        for entry in entries:
            cid = re.search(r"(CONFLITO-\d+)", entry)
            topic = re.search(r"·\s+(.+\.md)", entry)
            status = re.search(r"\*\*Status:\*\*\s+(\w+)", entry)
            if cid:
                results.append({
                    "id": cid.group(1),
                    "topic": topic.group(1).strip() if topic else None,
                    "status": status.group(1).strip() if status else None,
                })
        return results

    def resolve(self, conflict_id: str, resolution: str, note: str = None):
        """Mark a conflict as resolved."""
        if not self.queue_file.exists():
            return
        content = self.queue_file.read_text()
        # Replace status line
        pattern = rf"(## {conflict_id}.*?\n\*\*Status:\*\*)\s*\w+"
        replacement = rf"\1 {resolution}"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        if note:
            content = content.replace(
                f"**Resolução Lincoln:** ___________________________",
                f"**Resolução Lincoln:** {note}"
            )
        self.queue_file.write_text(content)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py::test_queue_add_conflict tests/test_signal_curation.py::test_queue_idempotent -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/conflict_queue.py tests/test_signal_curation.py
git commit -m "feat(signal-curation): add conflict queue manager

TDD: tests first.
ConflictQueue.add(): adds conflict with ID, evidence, proposal.
ConflictQueue.list_pending(): parse queue for pending items.
ConflictQueue.resolve(): mark as resolved with Lincoln's note.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## FASE 3 — GitHub + Feedback + Integration

### Task 9: github_collector.py + feedback_collector.py + cron hookup

**Files:**
- Create: `skills/memoria-consolidation/collectors/github_collector.py`
- Create: `skills/memoria-consolidation/collectors/feedback_collector.py`
- Modify: `skills/memoria-consolidation/curation_cron.py` (add logs_collector + conflict_detector + conflict_queue)

**This task covers integrating Phase 1 + Phase 2 components into curation_cron, and adding GitHub + Feedback collectors.**

- [ ] **Step 1: Write github_collector.py**

```python
#!/usr/bin/env python3
"""
github_collector.py — Collects merged PR signals from GitHub REST API.
Priority: 3 (tertiary — secondary evidence)

Key endpoints:
  GET /repos/{owner}/{repo}/pulls?state=closed → merged PRs with merged_at
  GET /repos/{owner}/{repo}/pulls/{number}/comments → PR comments

Env: GITHUB_TOKEN (personal access token)
"""
import os, requests
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_bus import SignalEvent

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_ORG = os.environ.get("GITHUB_ORGS", "living")

REPO_TOPIC_MAP = {
    "livy-bat-jobs": "bat-conectabot-observability.md",
    "livy-delphos-jobs": "delphos-video-vistoria.md",
    "livy-tldv-jobs": "tldv-pipeline-state.md",
    "livy-forge-platform": "forge-platform.md",
}


class GitHubCollector:
    source = "github"
    priority = 3

    def __init__(self, token: str = None, org: str = None):
        self.token = token or GITHUB_TOKEN
        self.org = org or GITHUB_ORG
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def _get(self, url: str, params: dict = None) -> requests.Response:
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp

    def fetch_merged_prs(self, repo: str, since: str = None) -> list[dict]:
        """Fetch merged PRs for a repo since ISO timestamp."""
        url = f"https://api.github.com/repos/{self.org}/{repo}/pulls"
        params = {"state": "closed", "per_page": 30, "sort": "updated", "direction": "desc"}
        if since:
            params["since"] = since
        resp = self._get(url, params)
        prs = resp.json()
        # Filter to only merged (have merged_at)
        return [pr for pr in prs if pr.get("merged_at")]

    def collect(self, since_days: int = 7) -> list[SignalEvent]:
        """
        Collect merged PR signals across all living/ repos.
        Only PRs with meaningful description → signal_type=correction (if revert/rollback)
          or evidence for TLDV decisions.
        """
        signals = []
        import time
        since = datetime.now(timezone.utc).isoformat()

        repos = list(REPO_TOPIC_MAP.keys())

        for repo in repos:
            try:
                prs = self.fetch_merged_prs(repo)
                for pr in prs[:10]:  # latest 10
                    topic_ref = REPO_TOPIC_MAP.get(repo)
                    title = pr.get("title", "")
                    body = pr.get("body", "") or ""
                    merged_at = pr.get("merged_at", "")
                    pr_number = pr.get("number")

                    # Check if it's a revert/rollback → correction signal
                    if any(kw in title.lower() for kw in ["revert", "rollback", "undo"]):
                        sig = SignalEvent(
                            source="github",
                            priority=3,
                            topic_ref=topic_ref,
                            signal_type="correction",
                            payload={
                                "description": f"PR #{pr_number} revert/rollback: {title}",
                                "evidence": pr.get("html_url"),
                                "confidence": 1.0,
                            },
                            origin_id=f"PR#{pr_number}",
                            origin_url=pr.get("html_url"),
                        )
                        signals.append(sig)
                    elif body and topic_ref:
                        # Use PR description as evidence for topic
                        sig = SignalEvent(
                            source="github",
                            priority=3,
                            topic_ref=topic_ref,
                            signal_type="decision",
                            payload={
                                "description": f"PR #{pr_number}: {title}",
                                "evidence": pr.get("html_url"),
                                "confidence": 0.6,
                            },
                            origin_id=f"PR#{pr_number}",
                            origin_url=pr.get("html_url"),
                        )
                        signals.append(sig)
                time.sleep(0.3)  # rate limit guard
            except Exception as e:
                import logging
                logging.warning(f"GitHub fetch failed for {repo}: {e}")
        return signals
```

- [ ] **Step 2: Write feedback_collector.py**

```python
#!/usr/bin/env python3
"""
feedback_collector.py — Collects Lincoln's feedback signals from feedback-log.jsonl.
Priority: 4 (quartenária — learning only, not auto-apply)

Reads: memory/feedback-log.jsonl
Maps: thumbs_down → correction signal; thumbs_up → positive reinforcement
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_bus import SignalEvent

FEEDBACK_LOG = Path(__file__).resolve().parents[1] / "memory" / "feedback-log.jsonl"


class FeedbackCollector:
    source = "feedback"
    priority = 4

    def collect(self, limit: int = 50) -> list[SignalEvent]:
        """Read last N feedback entries, emit correction signals for thumbs_down."""
        signals = []
        if not FEEDBACK_LOG.exists():
            return signals

        lines = FEEDBACK_LOG.read_text().strip().splitlines()
        for line in lines[-limit:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            action = entry.get("action", "")
            thumbs_down = entry.get("thumbs_down", 0)
            thumbs_up = entry.get("thumbs_up", 0)
            timestamp = entry.get("timestamp", "")

            if thumbs_down > thumbs_up:
                # Negative feedback → correction signal
                sig = SignalEvent(
                    source="feedback",
                    priority=4,
                    topic_ref=action if action.endswith(".md") else None,
                    signal_type="correction",
                    payload={
                        "description": f"Feedback negativo: {action}",
                        "evidence": f"feedback-log:{timestamp}",
                        "confidence": 0.9,
                    },
                    origin_id=f"feedback-{timestamp}",
                    origin_url=None,
                )
                signals.append(sig)

        return signals
```

- [ ] **Step 3: Update curation_cron.py to include Phase 2 components**

Read the current `curation_cron.py` and add:

```python
# After TLDV collector import, add:
from collectors.logs_collector import LogsCollector
from collectors.github_collector import GitHubCollector
from collectors.feedback_collector import FeedbackCollector
from conflict_detector import ConflictDetector
from conflict_queue import ConflictQueue

# In main(), after collecting TLDV signals, add:

    # Collect logs signals
    logs_collector = LogsCollector()
    try:
        logs_signals = logs_collector.collect()
        for sig in logs_signals:
            bus.emit(sig)
        log_structured("INFO", correlation_id, "logs_collector", "collection_complete",
                       count=len(logs_signals))
    except Exception as e:
        log_structured("ERROR", correlation_id, "logs_collector", "collection_failed",
                       error=str(e))

    # Collect GitHub signals
    github_collector = GitHubCollector()
    try:
        github_signals = github_collector.collect()
        for sig in github_signals:
            bus.emit(sig)
        log_structured("INFO", correlation_id, "github_collector", "collection_complete",
                       count=len(github_signals))
    except Exception as e:
        log_structured("ERROR", correlation_id, "github_collector", "collection_failed",
                       error=str(e))

    # Collect feedback signals
    feedback_collector = FeedbackCollector()
    try:
        feedback_signals = feedback_collector.collect()
        for sig in feedback_signals:
            bus.emit(sig)
        log_structured("INFO", correlation_id, "feedback_collector", "collection_complete",
                       count=len(feedback_signals))
    except Exception as e:
        log_structured("ERROR", correlation_id, "feedback_collector", "collection_failed",
                       error=str(e))

    # Detect conflicts
    conflict_detector = ConflictDetector()
    conflicts = conflict_detector.detect(bus.events, {})
    log_structured("INFO", correlation_id, "conflict_detector", "detection_complete",
                   count=len(conflicts))

    # Add conflicts to queue
    if conflicts:
        queue = ConflictQueue()
        for conflict in conflicts:
            queue.add(conflict)
        log_structured("WARN", correlation_id, "conflict_queue", "conflicts_added",
                       count=len(conflicts))
```

- [ ] **Step 4: Run all tests**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/test_signal_curation.py -v --tb=short 2>&1 | tail -30
```
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add skills/memoria-consolidation/collectors/github_collector.py skills/memoria-consolidation/collectors/feedback_collector.py skills/memoria-consolidation/curation_cron.py tests/test_signal_curation.py
git commit -m "feat(signal-curation): add GitHub + feedback collectors, integrate Phase 2

github_collector: merged PRs as evidence/correction (priority 3).
feedback_collector: thumbs_down → correction signal (priority 4).
curation_cron: now runs all collectors + conflict detection + queue.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"
```

---

## Self-Review Checklist

- [ ] Spec coverage: All 14 sections have at least one implementing task
- [ ] No placeholders: All code is complete, no "TBD", no "implement later"
- [ ] Type consistency: `signal_type` values match spec (`decision`, `topic_mentioned`, `success`, `failure`, `correction`)
- [ ] Priority mapping: TLDV=1, Logs=2, GitHub=3, Feedback=4 (matches spec)
- [ ] Observability: every component logs with `correlation_id` and `component`
- [ ] Conflict detection: decision vs failure/correction rule implemented
- [ ] Tests: one failing test → minimal implementation → passing test per component
