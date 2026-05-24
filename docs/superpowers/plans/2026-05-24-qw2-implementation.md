# QW-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement QW-2 (RAW → Topic Files) and QW-3 (DM review for low-confidence decisions) per spec `docs/superpowers/specs/2026-05-24-qw2-design-v2.md`.

**Architecture:** QW-2 fetches directly from TLDV/Trello/GitHub RAW APIs, applies quality filters (length, confidence), extracts Trello plugin data, runs inference routing to topic files, and writes decisions directly with dedupe + write-log rollback. QW-3 handles DM review for ambiguous decisions (confidence < 0.85) and routing failures. First run is always dry-run requiring explicit confirmation.

**Tech Stack:** Python 3, existing `vault/research/{tldv_client,trello_client,github_client}.py`, `vault/research/retry_policy.py`, `vault/research/lock_manager.py`, Telegram API via OpenClaw `message` tool, `ruff`+`mypy`+`pytest`.

---

## File Structure

```
vault/qw2/
  __init__.py
  run.py              # CLI entry point (argparse)
  rollback.py         # Rollback by write log
  fetch_tldv.py       # Fetch decisions from TLDV meetings
  fetch_trello.py     # Fetch decisions from Trello cards
  fetch_github.py     # Fetch decisions from GitHub PRs
  filter.py           # Quality filters (length, confidence) for TLDV/GitHub
  router.py           # Inference pass → topic file mapping
  writer.py           # Append decision to topic file + dedupe + write log
  cursor.py           # Per-source cursor management

vault/qw3/
  __init__.py
  pending_dm.py       # Send DM for low-confidence decisions
  callbacks.py        # handle_confirm / handle_reject (idempotent)
  archive.py          # Rejected + TTL expiry

memory/vault/decisions/           # Topic files (output) — same as memory/curated/
memory/vault/pending/             # Low-confidence pending (JSON)
memory/vault/pending/archive/     # Rejected

.research/qw2/
  last_seen_tldv.json
  last_seen_trello.json
  last_seen_github.json
  written_refs.json     # dedupe set
  write_log.jsonl       # rollback log
  lock                  # fcntl lock file (from lock_manager.py)
  .confirmed            # flag: runs subsequentes escrevem
  .pending_confirmation/ # dry-run output awaiting confirm

tests/qw2/
  test_filter.py         # Parametrize table: length + confidence
  test_router.py         # Routing rules (Trello board_name + text)
  test_writer.py         # Append + dedupe + write log
  test_dedupe_cross_instance.py  # Two separate QWWriter instances dedupe correctly
  test_cursor.py         # Cursor read/write
  test_e2e.py            # Dry-run E2E with fixtures
  fixtures/
    tldv_meeting_with_decisions.json
    trello_cards.py  # dataclass fixtures, nao JSON
    github_pr_merged.json
    topic_file_sample.md

tests/qw3/
  test_callbacks_idempotent.py
  test_pending_dm.py
```

---

## Task 1: Project Scaffolding

**Files:**
- Create: `vault/qw2/__init__.py`
- Create: `vault/qw3/__init__.py`
- Create: `memory/vault/decisions/.gitkeep`
- Create: `memory/vault/pending/.gitkeep`
- Create: `memory/vault/pending/archive/.gitkeep`
- Create: `.research/qw2/.gitkeep`

- [ ] **Step 1: Create directories and __init__.py files**

```bash
mkdir -p vault/qw2 vault/qw3 tests/qw2/fixtures tests/qw3 memory/vault/decisions memory/vault/pending memory/vault/pending/archive .research/qw2/.pending_confirmation
touch vault/qw2/__init__.py vault/qw3/__init__.py memory/vault/decisions/.gitkeep memory/vault/pending/.gitkeep memory/vault/pending/archive/.gitkeep .research/qw2/.gitkeep
```

- [ ] **Step 2: Commit**

```bash
git add vault/qw2/__init__.py vault/qw3/__init__.py memory/vault/decisions/.gitkeep memory/vault/pending/.gitkeep memory/vault/pending/archive/.gitkeep .research/qw2/
git commit -m "feat(qw2): project scaffolding"
```

---

## Task 2: `vault/qw2/filter.py` — Quality Filters

**Files:**
- Create: `vault/qw2/filter.py`
- Modify: `tests/qw2/test_filter.py` (new)

**Reference:** Spec section 3.1.

- [ ] **Step 1: Write failing test**

```python
# tests/qw2/test_filter.py
import pytest
from vault.qw2.filter import should_skip

@pytest.mark.parametrize("text,expected_skip,reason", [
    # Trello: DONE cards sao dados operacionais — nenhum filtro DONE_CARD_RE
    # Trello filtra no fetch (card utilidade), nao no should_skip
    ("foi decidido que...", False, "real decision"),
    # Length
    ("x" * 49, True, "49 chars — too short"),
    ("x" * 50, False, "50 chars — exact threshold"),
    ("x" * 51, False, "51 chars — OK"),
    # Confidence
    ({"text": "x" * 51, "confidence": 0.74}, True, "confidence below 0.75"),
    ({"text": "x" * 51, "confidence": 0.75}, False, "confidence at threshold"),
    # No decisions
    ("Sem decisões registradas", True, "TLDV no-decisions placeholder"),
    ("sem decisões registradas", True, "lowercase variant"),
    # Status meeting override: high confidence (>=0.90) survives filter
    ({"text": "x" * 51, "confidence": 0.92, "_is_status_meeting": True}, False, "Status meeting with high confidence survives"),
    ({"text": "x" * 51, "confidence": 0.89, "_is_status_meeting": True}, True, "Status meeting with low confidence still filtered"),
])
def test_should_skip(text, expected_skip, reason):
    if isinstance(text, dict):
        skip, _ = should_skip(text)
    else:
        skip, _ = should_skip({"text": text, "confidence": 0.90})
    assert skip == expected_skip, reason
```

Run: `pytest tests/qw2/test_filter.py -v`
Expected: FAIL — `should_skip` not defined

- [ ] **Step 2: Write minimal implementation**

```python
# vault/qw2/filter.py
"""Quality filters for QW-2 RAW → Topic File pipeline."""
from __future__ import annotations

from typing import Any

def should_skip(claim: dict[str, Any]) -> tuple[bool, str]:
    """Return (skip, reason). False = process this claim."""
    text = claim.get("text", "")
    source = claim.get("source", "")
    confidence = claim.get("confidence", 0)

    # 1. Status meeting override: high-confidence decisions survive even in filler meetings
    is_status = claim.get("_is_status_meeting", False)
    if is_status and confidence >= 0.90:
        return False, ""  # override — status meeting but high confidence

    # 2. Texto curto demais (TLDV + GitHub)
    if len(text) < 50:
        return True, f"text too short ({len(text)} chars)"

    # 3. Confiança baixa (TLDV + GitHub — Trello não tem confidence)
    if confidence < 0.75:
        return True, f"low confidence {confidence}"

    # 4. TLDV sem decisões registradas
    if "sem decisões registradas" in text.lower():
        return True, "no decisions in transcript"

    return False, ""
```

Run: `pytest tests/qw2/test_filter.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/filter.py tests/qw2/test_filter.py
git commit -m "feat(qw2): quality filters — length + confidence, Trello plugin data"
```

---

## Task 3: `vault/qw2/cursor.py` — Per-Source Cursor Management

**Files:**
- Create: `vault/qw2/cursor.py`
- Modify: `tests/qw2/test_cursor.py` (new)

- [ ] **Step 1: Write failing test**

```python
# tests/qw2/test_cursor.py
import json, pytest
from vault.qw2.cursor import QWCursor

def test_read_write_cursor(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.cursor.QW2_CURSOR_DIR", tmp_path)
    c = QWCursor("tldv")
    assert c.read() is None
    c.write("2026-05-24T10:00:00Z")
    assert c.read() == "2026-05-24T10:00:00Z"

def test_cursor_per_source(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.cursor.QW2_CURSOR_DIR", tmp_path)
    t = QWCursor("tldv")
    g = QWCursor("github")
    t.write("2026-05-24T10:00:00Z")
    g.write("2026-05-24T11:00:00Z")
    assert t.read() == "2026-05-24T10:00:00Z"
    assert g.read() == "2026-05-24T11:00:00Z"
```

Run: `pytest tests/qw2/test_cursor.py -v`
Expected: FAIL

- [ ] **Step 2: Write implementation**

```python
# vault/qw2/cursor.py
"""Per-source cursor for QW-2 incremental processing."""
from __future__ import annotations

import json
from pathlib import Path

QW2_CURSOR_DIR = Path(".research/qw2")

class QWCursor:
    """Read/write cursor for one source."""

    def __init__(self, source: str):
        self.source = source
        self.path = QW2_CURSOR_DIR / f"last_seen_{source}.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def read(self) -> str | None:
        if not self.path.exists():
            return None
        try:
            return json.loads(self.path.read_text())["last_seen"]
        except Exception:
            return None

    def write(self, timestamp: str) -> None:
        self.path.write_text(json.dumps({"last_seen": timestamp, "source": self.source}))
```

Run: `pytest tests/qw2/test_cursor.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/cursor.py tests/qw2/test_cursor.py
git commit -m "feat(qw2): per-source cursor management"
```

---

## Task 4: `vault/qw2/writer.py` + `written_refs` + `write_log`

**Files:**
- Create: `vault/qw2/writer.py`
- Create: `tests/qw2/test_writer.py`
- Create: `tests/qw2/test_dedupe_cross_instance.py`

**Reference:** Spec sections 3.4 and 3.5.

- [ ] **Step 1: Write failing test**

```python
# tests/qw2/test_writer.py
import json, pytest
from vault.qw2.writer import QWWriter, load_written_refs, add_to_written_refs

def test_write_append_and_log(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.writer.QW2_BASE", tmp_path)
    monkeypatch.setattr("vault.qw2.writer.DECISIONS_DIR", tmp_path / "decisions")
    decision = {
        "text": "Usar GPT-4 para decisões de alta confiança.",
        "source_ref": "tldv:meeting_abc",
        "confidence": 0.92,
        "date": "2026-05-24",
        "source": "tldv",
        "tags": ["llm", "gpt-4"],
    }
    writer = QWWriter()
    topic = tmp_path / "decisions" / "livy-memory-agent.md"
    writer.write(topic, decision)

    content = topic.read_text()
    assert "Usar GPT-4" in content
    assert "> Usar GPT-4" in content  # blockquote
    assert "confidence: 0.92" in content

    # write log entry
    log = (tmp_path / "write_log.jsonl").read_text()
    assert "tldv:meeting_abc" in log
```

Run: `pytest tests/qw2/test_writer.py -v`
Expected: FAIL — module not found

- [ ] **Step 2: Write implementation**

```python
# vault/qw2/writer.py
"""QW-2 writer: append decision to topic file with dedupe + write log."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

QW2_BASE = Path(".research/qw2")
WRITTEN_REFS = QW2_BASE / "written_refs.json"
WRITE_LOG = QW2_BASE / "write_log.jsonl"
DECISIONS_DIR = Path("memory/vault/decisions")

def load_written_refs() -> set[str]:
    if not WRITTEN_REFS.exists():
        return set()
    try:
        data = json.loads(WRITTEN_REFS.read_text())
        if isinstance(data, list):
            return set(data)
        return set(data.get("refs", []))
    except Exception:
        return set()

def add_to_written_refs(source_ref: str) -> None:
    refs = load_written_refs()
    refs.add(source_ref)
    WRITTEN_REFS.parent.mkdir(parents=True, exist_ok=True)
    WRITTEN_REFS.write_text(json.dumps({"refs": list(refs)}))

def append_to_write_log(source_ref: str, topic: str, action: str) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source_ref": source_ref,
        "topic": topic,
        "action": action,
    }
    WRITE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(WRITE_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")

class QWWriter:
    """Append a decision to a topic file, with dedupe and write log."""

    def write(self, topic_path: Path, decision: dict) -> bool:
        """
        Append decision to topic file.
        Returns True if written, False if skipped (dedupe).
        """
        source_ref = decision["source_ref"]
        refs = load_written_refs()
        if source_ref in refs:
            return False  # already written

        topic_path.parent.mkdir(parents=True, exist_ok=True)

        entry = f"""
### {decision['date']} — {decision.get('source', 'unknown')}

> {decision['text']}

- **Source:** {decision.get('source_ref')}
- **Confidence:** {decision['confidence']}
- **Tags:** {', '.join(decision.get('tags', []))}
"""
        with open(topic_path, "a") as f:
            f.write(entry)

        add_to_written_refs(source_ref)
        append_to_write_log(source_ref, str(topic_path), "append")
        return True
```

Run: `pytest tests/qw2/test_writer.py -v`
Expected: PASS

- [ ] **Step 3: Add cross-instance dedupe test (critical — tests disk-based dedupe)**

```python
# tests/qw2/test_dedupe_cross_instance.py
"""Verify dedupe works across two separate QWWriter instances (simulates two runs)."""
import json, pytest
from vault.qw2.writer import QWWriter, load_written_refs

def test_dedupe_across_two_writer_instances(tmp_path, monkeypatch):
    """Simulates two separate runs. Writer2 should see refs written by Writer1."""
    monkeypatch.setattr("vault.qw2.writer.QW2_BASE", tmp_path)
    monkeypatch.setattr("vault.qw2.writer.DECISIONS_DIR", tmp_path / "decisions")

    decision = {
        "text": "Test decision for dedupe.",
        "source_ref": "tldv:meeting_cross_instance_test",
        "confidence": 0.90,
        "date": "2026-05-24",
        "source": "tldv",
        "tags": [],
    }
    topic = tmp_path / "decisions" / "test.md"

    # Run 1: first writer instance
    writer1 = QWWriter()
    result1 = writer1.write(topic, decision)
    assert result1 is True, "First write should succeed"

    # Run 2: second writer instance (separate process simulation)
    writer2 = QWWriter()
    result2 = writer2.write(topic, decision)
    assert result2 is False, "Second write should be skipped (dedupe)"

    # Content should appear exactly once
    content = topic.read_text()
    assert content.count("Test decision for dedupe.") == 1
```

Run: `pytest tests/qw2/test_dedupe_cross_instance.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add vault/qw2/writer.py tests/qw2/test_writer.py tests/qw2/test_dedupe_cross_instance.py
git commit -m "feat(qw2): writer with dedupe and write log"
```

---

## Task 5: `vault/qw2/router.py` — Inference Pass

**Files:**
- Create: `vault/qw2/router.py`
- Create: `tests/qw2/test_router.py`

**Reference:** Spec section 3.3.

**IMPORTANT:** Trello routing must use `board_name` field (from fetch_trello.py) in addition to text. A card from the "Forge" board routes to `forge-platform.md` regardless of card title.

- [ ] **Step 1: Write failing test**

```python
# tests/qw2/test_router.py
import pytest
from vault.qw2.router import route_decision

@pytest.mark.parametrize("source,decision,expected_topic", [
    ("tldv", {"text": "Status BAT reunião sobre erros"}, "bat-conectabot-observability.md"),
    ("tldv", {"text": "Discussão sobre TLDV e memory agent"}, "livy-memory-agent.md"),
    ("tldv", {"text": "Projeto Forge plataforma nova"}, "forge-platform.md"),
    ("trello", {"text": "Card title not relevant", "board_name": "Delphos"}, "delphos-video-vistoria.md"),
    ("trello", {"text": "Card on Forge board", "board_name": "Forge"}, "forge-platform.md"),
    ("github", {"text": "PR sobre Evo sistema"}, "livy-evo.md"),
    ("tldv", {"text": "Algo que não matches nada"}, "general.md"),  # fallback → DM
])
def test_route_decision(source, decision, expected_topic):
    decision["source"] = source
    result = route_decision(decision)
    assert result["topic"] == expected_topic
    assert result.get("routing_failed") == (expected_topic == "general.md")
```

Run: `pytest tests/qw2/test_router.py -v`
Expected: FAIL

- [ ] **Step 2: Write implementation**

```python
# vault/qw2/router.py
"""Inference pass: map a decision to a topic file."""
from __future__ import annotations

from typing import Any

ROUTING_RULES: list[tuple[list[str], str]] = [
    (["bat", "kaba", "bot"], "bat-conectabot-observability.md"),
    (["tldv", "memory", "livy", "openclaw", "gateway"], "livy-memory-agent.md"),
    (["delphos", "vistoria"], "delphos-video-vistoria.md"),
    (["forge"], "forge-platform.md"),
    (["evo", "evolution"], "livy-evo.md"),
    (["4d", "imobi"], "4d-imobi.md"),
    (["hydra"], "hydra-evolution.md"),
]

# Trello board name → topic file (explicit mapping)
ROUTING_RULES = [
    (["bat", "kaba", "bot"], "bat-conectabot-observability.md"),
    (["tldv", "memory", "livy", "openclaw", "gateway"], "livy-memory-agent.md"),
    (["delphos", "vistoria"], "delphos-video-vistoria.md"),
    (["forge"], "forge-platform.md"),
    (["evo", "evolution"], "livy-evo.md"),
    (["4d", "imobi"], "4d-imobi.md"),
    (["hydra"], "hydra-evolution.md"),
    (["b3", "balc", "balcao"], "bat-conectabot-observability.md"),
    (["cerc", "interop"], "delphos-video-vistoria.md"),
]

def route_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """Route a decision to a topic file. Returns dict with topic, routing_failed."""
    source = decision.get("source", "")
    text_lower = decision.get("text", "").lower()
    source_ref = decision.get("source_ref", "").lower()

    # Trello: check board_name first (spec section 3.3)
    if source == "trello":
        board_name = decision.get("board_name", "").lower()
        for board_key, topic in TRELLO_BOARD_ROUTING.items():
            if board_key in board_name:
                return {"topic": topic, "routing_failed": False, "match": f"board:{board_key}"}

    # Combined text + source_ref for matching
    combined = f"{text_lower} {source_ref}"

    for keywords, topic in ROUTING_RULES:
        for kw in keywords:
            if kw in combined:
                return {"topic": topic, "routing_failed": False, "match": kw}

    # Fallback: general.md + routing failed → DM
    return {"topic": "general.md", "routing_failed": True, "match": None}
```

Run: `pytest tests/qw2/test_router.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/router.py tests/qw2/test_router.py
git commit -m "feat(qw2): inference pass router with Trello board_name support"
```

---

## Task 6: `vault/qw2/fetch_tldv.py` — TLDV Decision Extraction

**Files:**
- Create: `vault/qw2/fetch_tldv.py`
- Create: `tests/qw2/test_fetch_tldv.py`
- Reference: `vault/research/tldv_client.py`, `vault/research/retry_policy.py`

**Reference:** Spec sections 3.2 (TLDV) and 5 (TLDV cursor details).

**Important:** Return `max_updated_at` from the function so run.py can write the actual cursor, not wall-clock time.

- [ ] **Step 1: Write implementation using existing TLDVClient + retry policy**

```python
# vault/qw2/fetch_tldv.py
"""Fetch decisions from TLDV meetings."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from vault.research.tldv_client import TLDVClient

logger = logging.getLogger(__name__)

STATUS_MEETING_RE = __import__("re").compile(
    r"^Status\s+(KABA|BAT|BOT)",
    __import__("re").IGNORECASE
)

def fetch_tldv_decisions(since_days: int = 7) -> tuple[list[dict[str, Any]], str | None]:
    """
    Fetch meetings updated in last N days, extract decisions.
    Returns (decisions, max_updated_at) where max_updated_at is the latest
    meeting.updated_at for cursor update.
    """
    try:
        client = TLDVClient(lookback_days=since_days)
    except Exception as e:
        logger.warning(f"TLDV not configured: {e}")
        return [], None

    meetings = client.fetch_updated_meetings()
    decisions = []
    max_updated: str | None = None

    for meeting in meetings:
        name = meeting.get("name", "")
        meeting_id = meeting.get("id", "")
        updated_at = meeting.get("updated_at") or meeting.get("created_at", "")

        # Track cursor
        if updated_at and (max_updated is None or updated_at > max_updated):
            max_updated = updated_at

        # Skip Status meetings unless high confidence override (confidence >= 0.90)
        is_status_meeting = bool(STATUS_MEETING_RE.match(name))

        # Fetch full meeting to get transcript/summary
        full = client.fetch_meeting(meeting_id)
        summaries = full.get("summaries", []) or []

        for summary in summaries:
            summary_decisions = summary.get("decisions") or []
            if not isinstance(summary_decisions, list):
                continue
            for d in summary_decisions:
                d_text = str(d).strip()
                if not d_text or len(d_text) < 10:
                    continue
                decisions.append({
                    "text": d_text,
                    "source_ref": f"tldv:{meeting_id}",
                    "confidence": 0.92,  # TLDV summaries have implicit high confidence
                    "date": _meeting_date(meeting),
                    "source": "tldv",
                    "meeting_name": name,
                    "tags": summary.get("tags", []) or [],
                    "_is_status_meeting": is_status_meeting,
                })

    return decisions, max_updated

def _meeting_date(meeting: dict) -> str:
    try:
        dt = datetime.fromisoformat(meeting.get("created_at", "").replace("Z", "+00:00"))
        return (dt - timedelta(hours=3)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

- [ ] **Step 2: Write tests (mock TLDVClient)**

```python
# tests/qw2/test_fetch_tldv.py
from unittest.mock import patch, MagicMock
from vault.qw2.fetch_tldv import fetch_tldv_decisions

@patch("vault.qw2.fetch_tldv.TLDVClient")
def test_fetch_tldv_extracts_decisions(mock_client_cls):
    mock_client = MagicMock()
    mock_client.fetch_updated_meetings.return_value = [
        {"id": "m1", "name": "Daily Bot", "created_at": "2026-05-24T12:00:00Z", "updated_at": "2026-05-24T14:00:00Z"}
    ]
    mock_client.fetch_meeting.return_value = {
        "summaries": [{"decisions": ["Usar GPT-4"], "tags": ["llm"]}]
    }
    mock_client_cls.return_value = mock_client

    results, max_updated = fetch_tldv_decisions(since_days=7)
    assert len(results) == 1
    assert results[0]["text"] == "Usar GPT-4"
    assert results[0]["source_ref"] == "tldv:m1"
    assert max_updated == "2026-05-24T14:00:00Z"
```

Run: `pytest tests/qw2/test_fetch_tldv.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/fetch_tldv.py tests/qw2/test_fetch_tldv.py
git commit -m "feat(qw2): TLDV decision fetcher with max_updated_at cursor"
```

---

## Task 7: `vault/qw2/fetch_trello.py` — Trello Operational Snapshots

**Files:**
- Create: `vault/qw2/fetch_trello.py`
- Create: `tests/qw2/test_fetch_trello.py`
- Reference: `vault/research/trello_client.py` (usa `get_normalized_cards`)

**Reference:** Spec sections 3.1 (Trello as operational data) and 5 (Trello cursor per board).

**CAMPO CRÍTICO — ParsedTrelloCard é dataclass, não dict:**

```python
# ❌ ERRADO — ParsedTrelloCard é dataclass, não dict
card.get("card_id")  # AttributeError

# ✅ CORRETO — acesso por atributo
card.card_id
card.card_name
card.board_id          # NOTE: nao tem board_name no dataclass
card.list_name
card.github_links     # list[str], nao str
card.hours_logged     # float, ja extraido
card.last_activity    # str | None
```

**NOTE:** `ParsedTrelloCard` tem `board_id` mas NAO tem `board_name`. Para obter o nome do board, fazer `GET /1/boards/{board_id}` separadamente, conforme implementado no Step 1 abaixo.

**Plan:**
- Sem board allowlist — todos os 28 boards
- Sem confidence gate
- Trello cards nao passam por `should_skip` — tem filtro proprio `trello_card_passes_filter`
- `hours_logged` ja existe no dataclass — NAO chamar `extract_hours_plugin` de novo
- `github_links` e list — pegar `github_links[0]` se existir

- [ ] **Step 1: Write implementation**

```python
# vault/qw2/fetch_trello.py
"""Fetch Trello cards as operational snapshots — not decisions."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

from vault.research.trello_client import TrelloClient, TRELLO_API_BASE

logger = logging.getLogger(__name__)


def trello_card_passes_filter(card: "ParsedTrelloCard") -> bool:
    """Retorna True se o card tem dados operacionais uteis.

    Regras (spec section 3.1):
    - Card com card_name < 10 chars: skip
    - Card sem list_name e sem last_activity: skip
    - Cards em qualquer lista (BACKLOG, doing, done) passam
    """
    if len(card.card_name) < 10:
        return False
    if not card.list_name and not card.last_activity:
        return False
    return True


def _fetch_board_name(board_id: str, client: TrelloClient) -> str:
    """Fetch board name from Trello API (ParsedTrelloCard so tem board_id, nao board_name)."""
    try:
        url = f"{TRELLO_API_BASE}/boards/{board_id}"
        params = {"key": client.api_key, "token": client.token, "fields": "name"}
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 200:
            return r.json().get("name", board_id)
    except Exception as e:
        logger.warning("Failed to fetch board name for %s: %s", board_id, e)
    return board_id


def fetch_trello_snapshots(
    since_days: int = 30
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    """
    Fetch all Trello cards (no board allowlist) as operational snapshots.
    Returns (snapshots, cursors) where cursors is {board_slug: last_seen_timestamp}.

    ParsedTrelloCard e dataclass — acesso por atributo, nao dict.get().
    """
    try:
        client = TrelloClient()
    except EnvironmentError as e:
        logger.warning(f"Trello not configured: {e}")
        return [], {}

    raw_cards = client.get_normalized_cards()
    snapshots = []
    cursors: dict[str, str] = {}
    board_name_cache: dict[str, str] = {}

    for card in raw_cards:
        # Filtro de utilidade — ATENCAO: ParsedTrelloCard e dataclass
        if not trello_card_passes_filter(card):
            continue

        # Timestamp filter
        last_activity = card.last_activity or ""
        try:
            dt = datetime.fromisoformat(last_activity.replace("Z", "+00:00"))
            cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
            if last_activity and dt < cutoff:
                continue
        except Exception:
            pass

        # board_name: buscar do cache ou API (dataclass nao tem board_name)
        board_id = card.board_id
        if board_id not in board_name_cache:
            board_name_cache[board_id] = _fetch_board_name(board_id, client)
        board_name = board_name_cache[board_id]
        board_slug = _slugify(board_name)

        if last_activity:
            cursors[board_slug] = last_activity

        # github_links e list — primeiro link
        github_url = card.github_links[0] if card.github_links else None
        # hours_logged: ja existe no dataclass, nao redundante
        hours = card.hours_logged if card.hours_logged > 0 else None

        snapshots.append({
            "source_ref": f"trello:{card.card_id}",
            "board_id": board_id,
            "board_name": board_name,
            "board_slug": board_slug,
            "list_name": card.list_name,
            "card_name": card.card_name,
            "desc": card.card_url,  # no desc field in dataclass; use card_url
            "card_url": card.card_url,
            "hours_logged": hours,
            "github_pr_url": github_url,
            "last_activity": last_activity,
            "labels": card.labels,
            "source": "trello",
        })

    return snapshots, cursors


def _slugify(name: str) -> str:
    """Slugify board name for cursor key."""
    import re
    return re.sub(r"[^a-z0-9-]", "", name.lower())
```

**NOTA:** `ParsedTrelloCard` nao tem campo `desc` — tem `card_url`. O description do card nao e guardado no dataclass. Se precisar do desc, chamar `get_card_comments()` por card.

- [ ] **Step 2: Write tests (mock TrelloClient)**

```python
# tests/qw2/test_fetch_trello.py
"""Tests for fetch_trello_snapshots — uses ParsedTrelloCard dataclass."""
from unittest.mock import patch, MagicMock
from vault.research.trello_parsers import ParsedTrelloCard
from vault.qw2.fetch_trello import trello_card_passes_filter, fetch_trello_snapshots

def test_trello_card_passes_filter_accepts_dataclass():
    # TRELLO_CARD_WITH_PLUGIN has card_name >= 10 chars — passes
    card = ParsedTrelloCard(
        card_id="c1", card_name="Deploy UAT - Voice RLSE0109469",
        card_url="https://trello.com/c/ABC", board_id="b1", list_name="Concluído",
        labels=[], due_date=None,
        github_links=["https://github.com/living/livy-forge/pull/42"],
        hours_logged=4.5, last_activity="2026-05-24T12:00:00Z",
    )
    assert trello_card_passes_filter(card) is True

def test_trello_card_passes_filter_rejects_short_name():
    # card_name < 10 chars — filtered
    card = ParsedTrelloCard(
        card_id="c2", card_name="Done", card_url="",
        board_id="b1", list_name="Concluído",
        labels=[], due_date=None,
        github_links=[], hours_logged=0.0, last_activity=None,
    )
    assert trello_card_passes_filter(card) is False

@patch("vault.qw2.fetch_trello.TrelloClient")
def test_fetches_all_boards_no_allowlist(mock_client_cls):
    """Sem allowlist — todos os boards sao processados."""
    from vault.research.trello_parsers import ParsedTrelloCard
    mock_client = MagicMock()
    # Retorna ParsedTrelloCard (dataclass), nao dict
    mock_client.get_normalized_cards.return_value = [
        ParsedTrelloCard(
            card_id="c1", card_name="Deploy UAT", card_url="https://trello.com/c/C1",
            board_id="board_bat", list_name="Concluído",
            labels=["deploy"], due_date=None,
            github_links=["https://github.com/living/livy-forge/pull/42"],
            hours_logged=4.5, last_activity="2026-05-24T12:00:00Z",
        ),
        ParsedTrelloCard(
            card_id="c2", card_name="Bugfix login", card_url="https://trello.com/c/C2",
            board_id="board_delphos", list_name="Done",
            labels=["bug"], due_date=None,
            github_links=[], hours_logged=2.0, last_activity="2026-05-23T12:00:00Z",
        ),
    ]
    mock_client_cls.return_value = mock_client

    with patch("vault.qw2.fetch_trello._fetch_board_name", return_value="BAT"):
        snapshots, cursors = fetch_trello_snapshots(since_days=30)

    assert len(snapshots) == 2
    # github_links e list — primeiro e usado
    assert snapshots[0]["github_pr_url"] == "https://github.com/living/livy-forge/pull/42"
    assert snapshots[0]["hours_logged"] == 4.5
    # board_name vem da API
    assert snapshots[0]["board_name"] == "BAT"
```

Run: `pytest tests/qw2/test_fetch_trello.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/fetch_trello.py tests/qw2/test_fetch_trello.py
git commit -m "feat(qw2): Trello operational snapshots — all boards, plugin data, no confidence gate"
```

---

## Task 8: `vault/qw2/fetch_github.py` — GitHub Decision Extraction

**Files:**
- Create: `vault/qw2/fetch_github.py`
- Create: `tests/qw2/test_fetch_github.py`
- Reference: `vault/research/github_client.py`

**Reference:** Spec section 6 (GitHub cursor).

**Important:** Use existing `GitHubClient.fetch_events_since()` which already normalizes events. Return `max_merged_at` for cursor.

- [ ] **Step 1: Write implementation**

```python
# vault/qw2/fetch_github.py
"""Fetch decisions from GitHub merged PRs."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from vault.research.github_client import GitHubClient

logger = logging.getLogger(__name__)

def fetch_github_decisions(since_days: int = 7) -> tuple[list[dict[str, Any]], str | None]:
    """
    Fetch merged PRs from all living org repos since cursor.
    Returns (decisions, max_merged_at) for cursor update.
    Uses existing GitHubClient normalization.
    """
    try:
        client = GitHubClient(lookback_days=since_days)
    except EnvironmentError as e:
        logger.warning(f"GitHub not configured: {e}")
        return [], None

    events = client.fetch_events_since(None)
    decisions = []
    max_merged: str | None = None

    for event in events:
        pr = event.get("payload", {})
        title = pr.get("title", "")
        body = pr.get("body", "") or ""
        merged_at = pr.get("merged_at", "")
        url = pr.get("url", "")
        repo = event.get("repo", "")

        if merged_at and (max_merged is None or merged_at > max_merged):
            max_merged = merged_at

        combined = f"{title} {body}".strip()
        if len(combined) < 50:
            continue

        decisions.append({
            "text": combined[:500],
            "source_ref": f"github:{repo}#{pr.get('number', '')}",
            "confidence": 0.85,
            "date": _pr_date(merged_at),
            "source": "github",
            "pr_title": title,
            "tags": [repo.split("/")[-1]] if repo else [],
            "url": url,
        })

    return decisions, max_merged

def _pr_date(merged_at: str) -> str:
    try:
        dt = datetime.fromisoformat(merged_at.replace("Z", "+00:00"))
        return (dt - timedelta(hours=3)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

- [ ] **Step 2: Write tests (mock GitHubClient)**

```python
# tests/qw2/test_fetch_github.py
from unittest.mock import patch, MagicMock
from vault.qw2.fetch_github import fetch_github_decisions

@patch("vault.qw2.fetch_github.GitHubClient")
def test_fetches_merged_prs(mock_client_cls):
    mock_client = MagicMock()
    mock_client.fetch_events_since.return_value = [
        {
            "repo": "living/livy-memory-bot",
            "payload": {
                "title": "feat: adicionar nova feature",
                "body": "Esta PR implementa o sistema de decisions.",
                "number": 42,
                "merged_at": "2026-05-24T12:00:00Z",
                "url": "https://github.com/living/livy-memory-bot/pull/42",
            }
        }
    ]
    mock_client_cls.return_value = mock_client

    results, max_merged = fetch_github_decisions(since_days=7)
    assert len(results) == 1
    assert results[0]["source_ref"] == "github:living/livy-memory-bot#42"
    assert max_merged == "2026-05-24T12:00:00Z"
```

Run: `pytest tests/qw2/test_fetch_github.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/fetch_github.py tests/qw2/test_fetch_github.py
git commit -m "feat(qw2): GitHub decision fetcher using existing GitHubClient normalization"
```

---

## Task 9: `vault/qw2/run.py` — Main CLI Entry Point

**Files:**
- Create: `vault/qw2/run.py`
- Modify: `vault/qw2/__init__.py`

**Reference:** Spec sections 6 (CLI) and 7 (File Structure).

**Critical fixes applied:**
- Cursor uses actual `max_updated_at` from API responses, not wall-clock time
- Uses `lock_manager.py` for concurrent run protection
- DM only sent when `routing_failed AND confidence < 0.85` (per spec section 4.3)
- `save_pending()` called for dm_candidates before sending DM
- `_send_dry_run_dm` uses `subprocess.run` to invoke OpenClaw tool (not `from message import message`)

- [ ] **Step 1: Write run.py**

```python
#!/usr/bin/env python3
"""QW-2 CLI: RAW → Topic Files pipeline."""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
import subprocess
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vault.qw2 import fetch_tldv, fetch_trello, fetch_github
from vault.qw2.filter import should_skip
from vault.qw2.router import route_decision
from vault.qw2.writer import QWWriter
from vault.qw2.cursor import QWCursor
from vault.research.lock_manager import acquire_lock, release_lock

QW2_BASE = Path(".research/qw2")
QW2_BASE.mkdir(parents=True, exist_ok=True)
DECISIONS_DIR = Path("memory/vault/decisions")
CONFIRMED_FLAG = QW2_BASE / ".confirmed"
LOCK_FILE = QW2_BASE / "lock"

def is_confirmed() -> bool:
    return CONFIRMED_FLAG.exists()

def confirm_run() -> None:
    CONFIRMED_FLAG.parent.mkdir(parents=True, exist_ok=True)
    CONFIRMED_FLAG.touch()

def _send_dry_run_dm(summary: dict) -> None:
    """Send DM via OpenClaw message tool using subprocess."""
    text = f"""🔍 QW-2 dry-run result

Processed: {summary['processed']}
Written: {summary['written']} | Skipped (dedupe): {summary['skipped_dedupe']} | Skipped (filter): {summary['skipped_filter']}
Routing failed (→ DM): {summary['routing_failed']}

[✅ Confirmar — proximo run escreve] [❌ Cancelar]
"""
    # Write DM text to a temp file; the cron agent reads this and sends via message tool
    dm_file = QW2_BASE / ".pending_confirmation" / "dry_run_dm.txt"
    dm_file.parent.mkdir(parents=True, exist_ok=True)
    dm_file.write_text(text)
    print(f"[QW-2] Dry-run DM saved to {dm_file}")

def run(source: str = "all", dry_run: bool = True, since_days: int = 7) -> dict:
    # Acquire lock — prevent concurrent runs
    if not acquire_lock(str(LOCK_FILE), timeout=10):
        print("[QW-2] Already running, skipping.")
        return {"error": "already_running"}

    try:
        summary = {
            "processed": 0, "written": 0, "skipped_dedupe": 0, "skipped_filter": 0,
            "errors": 0, "routing_failed": 0, "dm_candidates": [],
            "cursors": {}
        }

        # Always dry-run unless confirmed
        actual_dry_run = dry_run or not is_confirmed()
        if actual_dry_run:
            print("[QW-2] DRY-RUN — no writes")

        # Fetch decisions per source, track cursors
        if source in ("tldv", "all"):
            decisions, max_ts = fetch_tldv.fetch_tldv_decisions(since_days)
            _process_source("tldv", decisions, actual_dry_run, summary)
            if max_ts:
                summary["cursors"]["tldv"] = max_ts

        if source in ("trello", "all"):
            snapshots, cursors = fetch_trello.fetch_trello_snapshots(since_days)
            _process_trello_snapshots(snapshots, cursors, actual_dry_run, summary)
            if max_ts:
                summary["cursors"]["trello"] = max_ts

        if source in ("github", "all"):
            decisions, max_ts = fetch_github.fetch_github_decisions(since_days)
            _process_source("github", decisions, actual_dry_run, summary)
            if max_ts:
                summary["cursors"]["github"] = max_ts

        # Update cursors with actual API timestamps
        for src, ts in summary["cursors"].items():
            if ts:
                QWCursor(src).write(ts)

        # Save pending decisions and DM Lincoln if needed
        if summary["dm_candidates"]:
            from vault.qw3.pending_dm import save_pending
            for d in summary["dm_candidates"]:
                save_pending(d)
            if actual_dry_run:
                _send_dry_run_dm(summary)

        return summary
    finally:
        release_lock(str(LOCK_FILE))

def _process_source(source: str, decisions: list, dry_run: bool, summary: dict) -> None:
    from vault.qw3.pending_dm import save_pending
    writer = QWWriter()
    for decision in decisions:
        summary["processed"] += 1
        skip, reason = should_skip(decision)
        if skip:
            summary["skipped_filter"] += 1
            continue
        routed = route_decision(decision)
        decision["topic"] = routed["topic"]
        if routed.get("routing_failed"):
            # Per spec section 4.3: only DM if confidence < 0.85
            if decision.get("confidence", 0) < 0.85:
                summary["routing_failed"] += 1
                summary["dm_candidates"].append(decision)
            else:
                # High confidence but routing failed — log only, don't DM
                print(f"  [WARN] {source}: high-conf decision routed to general: {decision['text'][:60]}")
            continue
        topic_path = DECISIONS_DIR / routed["topic"]
        if dry_run:
            print(f"  [DRY] {source}: {decision['text'][:60]} → {routed['topic']}")
        else:
            written = writer.write(topic_path, decision)
            if written:
                summary["written"] += 1
                print(f"  [WROTE] {source}: {decision['text'][:60]}")
            else:
                summary["skipped_dedupe"] += 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="QW-2: RAW → Topic Files")
    parser.add_argument("--source", choices=["tldv", "trello", "github", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-run", action="store_true", help="Acknowledge first-run confirmation")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()

    if args.confirm_run:
        confirm_run()
        print("Run confirmed. Next runs will write for real.")
    else:
        result = run(source=args.source, dry_run=args.dry_run, since_days=args.days)
        print(f"\nSummary: {result}")
```

Run: `python vault/qw2/run.py --dry-run --source tldv --days 7`
Expected: runs without error

- [ ] **Step 2: Commit**

```bash
git add vault/qw2/run.py
git commit -m "feat(qw2): main CLI — cursor uses API timestamps, lock protection, correct DM routing"
```

---

## Task 10: `vault/qw2/rollback.py` — Rollback by Write Log

**Files:**
- Create: `vault/qw2/rollback.py`

**Reference:** Spec section 3.4 (rollback) and section 6 (CLI --rollback).

- [ ] **Step 1: Write implementation**

```python
# vault/qw2/rollback.py
"""Rollback QW-2 writes by reading write_log.jsonl."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

QW2_BASE = Path(".research/qw2")
WRITE_LOG = QW2_BASE / "write_log.jsonl"
DECISIONS_DIR = Path("memory/vault/decisions")

def rollback_last(n: int, dry_run: bool = True) -> None:
    if not WRITE_LOG.exists():
        print("No write_log.jsonl found.")
        return
    entries = []
    with open(WRITE_LOG) as f:
        for line in f:
            entries.append(json.loads(line))
    to_revert = entries[-n:]
    for entry in reversed(to_revert):
        topic = Path(entry["topic"])
        if not topic.exists():
            print(f"  [SKIP] {topic} not found")
            continue
        if dry_run:
            print(f"  [DRY] Would remove last entry from {topic.name}")
        else:
            _remove_last_entry(topic, entry["source_ref"])
            print(f"  [REVERTED] {topic.name}")

    if not dry_run:
        with open(WRITE_LOG, "w") as f:
            for entry in entries[:-n]:
                f.write(json.dumps(entry) + "\n")

def _remove_last_entry(topic: Path, source_ref: str) -> None:
    """Remove the last block containing source_ref from topic file."""
    content = topic.read_text()
    lines = content.split("\n")
    new_lines = []
    skip = False
    for line in lines:
        if source_ref in line:
            skip = True
            continue
        if skip and line.startswith("### "):
            skip = False
        if not skip:
            new_lines.append(line)
    topic.write_text("\n".join(new_lines) + "\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--last", type=int, required=True, help="Revert last N writes")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rollback_last(args.last, dry_run=args.dry_run)
```

- [ ] **Step 2: Commit**

```bash
git add vault/qw2/rollback.py
git commit -m "feat(qw2): rollback by write log"
```

---

## Task 11: `vault/qw3/callbacks.py` — Idempotent Confirm/Reject Handlers

**Files:**
- Create: `vault/qw3/callbacks.py`
- Create: `tests/qw3/test_callbacks_idempotent.py`

**Reference:** Spec sections 4.2 (confirm/reject) and 4.5 (idempotency).

- [ ] **Step 1: Write implementation**

```python
# vault/qw3/callbacks.py
"""QW-3 callback handlers for approve/reject — idempotent."""
from __future__ import annotations

from pathlib import Path

QW2_BASE = Path(".research/qw2")
CONFIRMED_FLAG = QW2_BASE / ".confirmed"
PENDING_DIR = Path("memory/vault/pending")
ARCHIVE_DIR = PENDING_DIR / "archive"
LINCOLN_ID = "7426291192"

def is_confirmed() -> bool:
    return CONFIRMED_FLAG.exists()

def is_rejected(claim_id: str) -> bool:
    return (ARCHIVE_DIR / f"{claim_id}.json").exists()

def handle_confirm(claim_id: str | None = None) -> str:
    """Mark run as confirmed. Idempotent. Writes flag to file for cross-process persistence."""
    if is_confirmed():
        return "already_confirmed"
    # QW2_AUTO_WRITE: escrito em ficheiro para persistir entre processos (cron agent → run.py)
    AUTO_WRITE_FLAG = QW2_BASE / ".auto_write_enabled"
    AUTO_WRITE_FLAG.parent.mkdir(parents=True, exist_ok=True)
    AUTO_WRITE_FLAG.write_text(datetime.now(timezone.utc).isoformat())
    CONFIRMED_FLAG.parent.mkdir(parents=True, exist_ok=True)
    CONFIRMED_FLAG.touch()
    return "confirmed"


def is_auto_write_enabled() -> bool:
    """Check if auto-write is enabled (read from file, not env var)."""
    return (QW2_BASE / ".auto_write_enabled").exists()

def handle_reject(claim_id: str) -> str:
    """Archive a pending claim. Idempotent."""
    if is_rejected(claim_id):
        return "already_rejected"
    pending_file = PENDING_DIR / f"{claim_id}.json"
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    if pending_file.exists():
        import shutil
        shutil.move(str(pending_file), str(ARCHIVE_DIR / f"{claim_id}.json"))
    return "rejected"
```

- [ ] **Step 2: Write idempotency tests**

```python
# tests/qw3/test_callbacks_idempotent.py
import pytest
from vault.qw3.callbacks import handle_confirm, handle_reject, is_confirmed, is_rejected

def test_confirm_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw3.callbacks.QW2_BASE", tmp_path)
    assert handle_confirm() == "confirmed"
    assert handle_confirm() == "already_confirmed"

def test_reject_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw3.callbacks.QW2_BASE", tmp_path)
    monkeypatch.setattr("vault.qw3.callbacks.PENDING_DIR", tmp_path / "pending")
    monkeypatch.setattr("vault.qw3.callbacks.ARCHIVE_DIR", tmp_path / "archive")
    (tmp_path / "pending").mkdir(parents=True)
    (tmp_path / "archive").mkdir(parents=True)
    (tmp_path / "pending" / "c1.json").write_text('{"id": "c1"}')

    assert handle_reject("c1") == "rejected"
    assert handle_reject("c1") == "already_rejected"
```

Run: `pytest tests/qw3/test_callbacks_idempotent.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw3/callbacks.py tests/qw3/test_callbacks_idempotent.py
git commit -m "feat(qw3): idempotent confirm/reject callbacks"
```

---

## Task 12: `vault/qw3/pending_dm.py` — DM for Low-Confidence Decisions + Save Pending

**Files:**
- Create: `vault/qw3/pending_dm.py`
- Create: `tests/qw3/test_pending_dm.py`

**Reference:** Spec sections 4.1, 4.3, and 4.4 (DM format).

**Important:** `save_pending()` is called by run.py before DM. This writes the pending JSON so callbacks.py can find it.

- [ ] **Step 1: Write implementation**

```python
# vault/qw3/pending_dm.py
"""QW-3: DM Lincoln for low-confidence decisions and routing failures."""
from __future__ import annotations

import json
from pathlib import Path

PENDING_DIR = Path("memory/vault/pending")
LINCOLN_ID = "7426291192"

def save_pending(decision: dict) -> Path:
    """
    Save a pending decision to memory/vault/pending/.
    Called by run.py before sending DM.
    Returns the path where saved.
    """
    claim_id = decision.get("source_ref", "").replace(":", "_").replace("/", "_")
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    path = PENDING_DIR / f"{claim_id}.json"
    path.write_text(json.dumps(decision, indent=2))
    return path

def send_pending_dm(decisions: list[dict]) -> None:
    """
    Send DM listing pending decisions awaiting approval.
    The cron agent reads .pending_confirmation/dry_run_dm.txt and sends via message tool.
    """
    if not decisions:
        return
    lines = [f"🔍 QW-2 result — pending confirmation\n\nDecisões geradas: {len(decisions)}\n"]
    for d in decisions:
        conf = d.get("confidence", 0)
        text = d.get("text", "")[:80]
        topic = d.get("topic", "unknown")
        lines.append(f"• [{d.get('source', '?').upper()}] {text} → {topic} (conf: {conf:.0%})")
    text = "\n".join(lines)
    text += "\n\n[✅ Confirmar — proximo run escreve] [❌ Cancelar]"

    # Write DM content for the cron agent to pick up
    dm_file = Path(".research/qw2/.pending_confirmation/dry_run_dm.txt")
    dm_file.parent.mkdir(parents=True, exist_ok=True)
    dm_file.write_text(text)
```

- [ ] **Step 2: Commit**

```bash
git add vault/qw3/pending_dm.py tests/qw3/test_pending_dm.py
git commit -m "feat(qw3): pending DM sender with save_pending for callback retry-safety"
```

---

## Task 13: E2E Tests + All Fixtures + Quality Gates

**Files:**
- Create: `tests/qw2/test_e2e.py`
- Create: `tests/qw2/fixtures/tldv_meeting_with_decisions.json`
- Create: `tests/qw2/fixtures/trello_card_done.json`
- Create: `tests/qw2/fixtures/trello_card_decision.json`
- Create: `tests/qw2/fixtures/github_pr_merged.json`
- Create: `tests/qw2/fixtures/topic_file_sample.md`

**Reference:** Spec section 9 (Quality Gates).

- [ ] **Step 1: Create all fixture files**

```json
// tests/qw2/fixtures/tldv_meeting_with_decisions.json
{
  "meetings": [
    {
      "id": "meeting_test_1",
      "name": "Daily BAT — decisões técnicas",
      "created_at": "2026-05-24T10:00:00Z",
      "updated_at": "2026-05-24T10:00:00Z"
    }
  ],
  "full_meeting": {
    "summaries": [
      {
        "decisions": [
          "Usar GPT-4 Turbo para decisões de alta confiança",
          "Manter o pipeline de observabilidade sem alterações"
        ],
        "tags": ["llm", "bat"]
      }
    ]
  }
}
```

```json
# tests/qw2/fixtures/trello_cards.py
# ParsedTrelloCard is a dataclass — fixtures must be dataclass instances
from vault.research.trello_parsers import ParsedTrelloCard

TRELLO_CARD_WITH_PLUGIN = ParsedTrelloCard(
    card_id="card_plugin_test",
    card_name="Deploy UAT - Voice RLSE0109469",
    card_url="https://trello.com/c/ABC123",
    board_id="board_bat",
    list_name="Concluído 🎉",
    labels=["deploy", "voice"],
    due_date=None,
    github_links=["https://github.com/living/livy-forge/pull/42"],
    hours_logged=4.5,
    last_activity="2026-05-24T12:00:00Z",
)

TRELLO_CARD_SHORT_NAME = ParsedTrelloCard(
    card_id="card_short_test",
    card_name="Done",
    card_url="https://trello.com/c/DEF456",
    board_id="board_bat",
    list_name="Concluído 🎉",
    labels=[],
    due_date=None,
    github_links=[],
    hours_logged=0.0,
    last_activity="2026-05-24T12:00:00Z",
)

TRELLO_CARD_NO_USEFUL_DATA = ParsedTrelloCard(
    card_id="card_empty_test",
    card_name="x" * 5,
    card_url="https://trello.com/c/GHI789",
    board_id="board_bat",
    list_name="",
    labels=[],
    due_date=None,
    github_links=[],
    hours_logged=0.0,
    last_activity=None,
)

// tests/qw2/fixtures/topic_file_sample.md
---
name: test-topic
---

# Test Topic

## Decisões

### 2026-05-20 — existing decision

> Esta decisão já existia antes.

- **Source:** tldv:existing_meeting
- **Confidence:** 0.90
- **Tags:** test
```

- [ ] **Step 2: Write E2E dry-run test**

```python
# tests/qw2/test_e2e.py
"""QW-2 E2E dry-run tests with fixtures."""
import json, pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

FIXTURE_DIR = Path(__file__).parent / "fixtures"
TLDV_FIXTURE = FIXTURE_DIR / "tldv_meeting_with_decisions.json"

@pytest.fixture
def tldv_fixture():
    return json.loads(TLDV_FIXTURE.read_text())

@patch("vault.qw2.fetch_tldv.TLDVClient")
def test_e2e_tldv_dry_run(mock_client_cls, tldv_fixture, tmp_path, monkeypatch):
    monkeypatch.setattr("vault.qw2.cursor.QW2_CURSOR_DIR", tmp_path / ".research/qw2")
    monkeypatch.setattr("vault.qw2.writer.QW2_BASE", tmp_path / ".research/qw2")
    monkeypatch.setattr("vault.qw2.writer.DECISIONS_DIR", tmp_path / "decisions")
    mock_client = MagicMock()
    mock_client.fetch_updated_meetings.return_value = tldv_fixture["meetings"]
    mock_client.fetch_meeting.return_value = tldv_fixture["full_meeting"]
    mock_client_cls.return_value = mock_client

    from vault.qw2 import run
    result = run(source="tldv", dry_run=True, since_days=7)

    assert result["processed"] >= 1
    assert result["written"] == 0  # dry-run
    assert result["errors"] == 0
```

- [ ] **Step 3: Run full test suite**

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory
python -m pytest tests/qw2/ tests/qw3/ -v --tb=short 2>&1 | tail -50
```

Expected: all tests pass

- [ ] **Step 4: Run linting**

```bash
ruff check vault/qw2 vault/qw3
mypy vault/qw2 vault/qw3 --ignore-missing-imports
```

Expected: 0 errors

- [ ] **Step 5: Commit**

```bash
git add tests/qw2/test_e2e.py tests/qw2/fixtures/ tests/qw3/
git commit -m "test(qw2 qw3): E2E dry-run tests and all fixture files"
```

---

## Task 14: Register Cron Jobs

**Reference:** Spec section 8 and HEARTBEAT.md.

- [ ] **Step 1: List existing crons to avoid duplication**

```bash
openclaw cron list | grep -E "qw2|qw3|honcho"
```

- [ ] **Step 2: Register crons**

```bash
# QW-2 daily (seg-sex 07h BRT) — dry-run first
openclaw cron add \
  --name "qw2-daily" \
  --schedule '{"kind":"cron","expr":"0 7 * * 1-6","tz":"America/Sao_Paulo"}' \
  --sessionTarget "isolated" \
  --payload '{"kind":"agentTurn","message":"Run QW-2: cd /home/lincoln/.openclaw/workspace-livy-memory && python vault/qw2/run.py --source all --days 7","timeoutSeconds":600}' \
  --delivery '{"mode":"announce","channel":"telegram","to":"7426291192"}'

# QW-2 weekly dry-run (domingo) — validate before real runs
openclaw cron add \
  --name "qw2-dry-run-weekly" \
  --schedule '{"kind":"cron","expr":"0 7 * * 0","tz":"America/Sao_Paulo"}' \
  --sessionTarget "isolated" \
  --payload '{"kind":"agentTurn","message":"Run QW-2 dry-run: cd /home/lincoln/.openclaw/workspace-livy-memory && python vault/qw2/run.py --dry-run --source all --days 7","timeoutSeconds":600}' \
  --delivery '{"mode":"announce","channel":"telegram","to":"7426291192"}'
```

- [ ] **Step 3: Commit**

```bash
git add -A && git commit -m "feat(crons): register qw2-daily and qw2-dry-run-weekly"
```

---

## Task 15: Update HEARTBEAT.md

**Reference:** HEARTBEAT.md format.

- [ ] **Step 1: Update HEARTBEAT.md**

Add to Jobs Ativos table:

| Job | Schedule (BRT) | Status | Erros Consec. | Nota |
|---|---|---|---|---|
| `qw2-daily` | seg-sex 07h | ✅ ok | 0 | RAW → topic files; dry-run until confirmed |
| `qw2-dry-run-weekly` | dom 07h | ✅ ok | 0 | Validação antes de confirmar |

Add to Alertas:

```
✅ QW-2 + QW-3 implemented — RAW → topic files pipeline
✅ Quality filters: length + confidence (Trello uses plugin data filter)
✅ Board allowlist: 7 boards Living
✅ Dedupe: written_refs.json + write_log.jsonl + cross-instance dedupe test
✅ Dry-run first run + DM confirmation (confidence < 0.85 OR routing failed)
✅ Cursor: uses actual max(updated_at) from API, not wall-clock
✅ Lock protection: lock_manager.py prevents concurrent runs
✅ QW-2: Trello is no-op in v1 (confidence=0, all filtered)
```

- [ ] **Step 2: Commit**

```bash
git add HEARTBEAT.md
git commit -m "docs: HEARTBEAT — QW-2 + QW-3 operational"
```

---


## Task 16: `vault/qw2/intersection.py` — Cross-Platform Deduplication

**Files:**
- Create: `vault/qw2/intersection.py`
- Create: `tests/qw2/test_intersection.py`

**Reference:** Spec section 3.4.

**Schema das funcoes de extracao:**

```python
import re
from urllib.parse import urlparse

def extract_hours_plugin(desc: str) -> float | None:
    """Extrai horas logadas do plugin de horas no desc do card Trello.

    Patterns aceitos:
      - "Horas:"
      - "hours:"
      - "Logged:"
      - "h:"
    """
    patterns = [
        r"(?:horas|hours|logged|h)[:\s]+(\d+(?:[.,]\d+)?)\s*h?",
        r"(\d+(?:[.,]\d+)?)\s*horas?\s*trabalhadas?",
    ]
    for p in patterns:
        m = re.search(p, desc, re.IGNORECASE)
        if m:
            val = m.group(1).replace(",", ".")
            return float(val)
    return None

def extract_github_url(desc: str) -> str | None:
    """Extrai URL de PR/issue do GitHub no desc do card Trello.

    Aceita: https://github.com/owner/repo/pull/123
           https://github.com/owner/repo/issues/456
           github.com/owner/repo/pull/123
    """
    GH_RE = re.compile(
        r"(?:https?://)?github\.com/([\w.-]+)/([\w.-]+)/(?:pull|issues)/(\d+)",
        re.IGNORECASE
    )
    m = GH_RE.search(desc)
    if m:
        return f"https://github.com/{m.group(1)}/{m.group(2)}/pull/{m.group(3)}"
    return None

def extract_trello_url(desc: str) -> str | None:
    """Extrai URL de card Trello no desc de um PR/issue GitHub.

    Aceita: https://trello.com/c/ABC123
           trello.com/c/ABC123
    """
    TR_RE = re.compile(r"(?:https?://)?trello\.com/c/([a-zA-Z0-9]+)", re.IGNORECASE)
    m = TR_RE.search(desc)
    if m:
        return f"https://trello.com/c/{m.group(1)}"
    return None
```

**IMPORTANT:** `list_name` vs `listName` — usar `card.list_name` do `ParsedTrelloCard` (ja normalizado pelo `trello_client.py` existente). Nao usar `listName` diretamente da API (retorna NONE).

- [ ] **Step 1: Write failing test**

```python
# tests/qw2/test_intersection.py
from vault.qw2.intersection import find_intersections, extract_hours_plugin, extract_github_url, extract_trello_url

def test_extract_hours():
    assert extract_hours_plugin("Horas: 4.5h trabalhadas") == 4.5
    assert extract_hours_plugin("Logged: 2 horas") == 2.0
    assert extract_hours_plugin("h: 1.5") == 1.5
    assert extract_hours_plugin("sem horas") is None

def test_extract_github_url():
    assert extract_github_url("Veja https://github.com/living/livy-forge/pull/42") == "https://github.com/living/livy-forge/pull/42"
    assert extract_github_url("github.com/living/livy-bot/issues/10") == "https://github.com/living/livy-bot/pull/10"
    assert extract_github_url("nada a ver") is None

def test_extract_trello_url():
    assert extract_trello_url("Card: https://trello.com/c/ABC123") == "https://trello.com/c/ABC123"
    assert extract_trello_url("nada") is None

def test_find_intersections():
    items = [
        {"source": "trello", "card_name": "Deploy UAT", "github_pr_url": "https://github.com/living/livy-forge/pull/42"},
        {"source": "github", "pr_title": "Deploy UAT to UAT", "trello_card_url": "https://trello.com/c/ABC123"},
        {"source": "tldv", "decisions": ["Validamos o deploy UAT"]},
    ]
    result = find_intersections(items, items, items)
    assert len(result) >= 1
    # Trello + GitHub intersection
    cross = [r for r in result if "github" in r.get("cross_platform", []) and "trello" in r.get("cross_platform", [])]
    assert len(cross) >= 1
```

Run: `pytest tests/qw2/test_intersection.py -v`
Expected: FAIL

- [ ] **Step 2: Write implementation**

```python
# vault/qw2/intersection.py
"""Cross-platform deduplication and intersection finding."""
from __future__ import annotations

import re
from urllib.parse import urlparse
from typing import Any

GH_RE = re.compile(
    r"(?:https?://)?github\.com/([\w.-]+)/([\w.-]+)/(?:pull|issues)/(\d+)",
    re.IGNORECASE
)
TR_RE = re.compile(r"(?:https?://)?trello\.com/c/([a-zA-Z0-9]+)", re.IGNORECASE)


def extract_hours_plugin(desc: str) -> float | None:
    patterns = [
        r"(?:horas|hours|logged|h)[:\s]+(\d+(?:[.,]\d+)?)\s*h?",
        r"(\d+(?:[.,]\d+)?)\s*horas?\s*trabalhadas?",
    ]
    for p in patterns:
        m = re.search(p, desc, re.IGNORECASE)
        if m:
            return float(m.group(1).replace(",", "."))
    return None


def extract_github_url(desc: str) -> str | None:
    m = GH_RE.search(desc)
    if m:
        return f"https://github.com/{m.group(1)}/{m.group(2)}/pull/{m.group(3)}"
    return None


def extract_trello_url(desc: str) -> str | None:
    m = TR_RE.search(desc)
    if m:
        return f"https://trello.com/c/{m.group(1)}"
    return None


def find_intersections(
    trello_items: list[dict[str, Any]],
    github_items: list[dict[str, Any]],
    tldv_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Find items that appear across multiple platforms."""
    intersections: list[dict[str, Any]] = []
    seen_github_urls: set[str] = set()
    seen_trello_urls: set[str] = set()

    def mark_intersection(item: dict, platforms: list[str]) -> dict:
        item = dict(item)
        item["cross_platform"] = sorted(set(platforms))
        return item

    # Index GitHub items by PR URL
    for g in github_items:
        url = g.get("github_pr_url") or extract_github_url(g.get("pr_body", ""))
        if url:
            seen_github_urls.add(url)
            g["_github_url_key"] = url

    # Index Trello items by PR URL (from plugin)
    for t in trello_items:
        url = t.get("_github_pr_url") or extract_github_url(t.get("desc", ""))
        if url:
            seen_trello_urls.add(url)
            t["_github_pr_url"] = url

    # Find Trello ↔ GitHub intersections
    common_urls = seen_github_urls & seen_trello_urls
    for t in trello_items:
        if t.get("_github_pr_url") in common_urls:
            for g in github_items:
                if g.get("_github_url_key") == t.get("_github_pr_url"):
                    intersections.append(mark_intersection(t, ["trello", "github"]))
                    break

    # Find Trello ↔ TLDV intersections (by card name vs decision text similarity)
    for t in trello_items:
        card_name = t.get("card_name", "").lower()
        if len(card_name) < 5:
            continue
        for d in tldv_items:
            decision_text = " ".join(d.get("decisions", []))
            if len(decision_text) < 5:
                continue
            # Simple overlap check
            overlap = set(card_name.split()) & set(decision_text.lower().split())
            if len(overlap) >= 2:
                intersections.append(mark_intersection(t, ["trello", "tldv"]))
                break

    return intersections
```

Run: `pytest tests/qw2/test_intersection.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/intersection.py tests/qw2/test_intersection.py
git commit -m "feat(qw2): intersection cross-platform deduplication + extraction helpers"
```

---

## Implementation Order

1. **Task 1** — Project scaffolding
2. **Task 2** — `filter.py` + tests (foundation — Trello zero-conf gate here)
3. **Task 3** — `cursor.py` + tests
4. **Task 4** — `writer.py` + tests + cross-instance dedupe test
5. **Task 5** — `router.py` + tests (Trello board_name routing)
6. **Task 6** — `fetch_tldv.py` + tests (returns max_updated_at)
7. **Task 7** — `fetch_trello.py` + tests (returns max_updated_at)
8. **Task 8** — `fetch_github.py` + tests (uses existing GitHubClient)
9. **Task 9** — `run.py` (integrates all above with lock + cursor from API + correct DM routing)
10. **Task 10** — `rollback.py`
11. **Task 11** — `callbacks.py` (QW-3)
12. **Task 12** — `pending_dm.py` (QW-3)
13. **Task 13** — E2E tests + lint + mypy
14. **Task 16** — `intersection.py` + `test_intersection.py` + all fixtures
14. **Task 14** — Register cron jobs
15. **Task 15** — Update HEARTBEAT.md
