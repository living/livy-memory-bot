# QW-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement QW-2 (RAW → Topic Files) and QW-3 (DM review for low-confidence decisions) per spec `docs/superpowers/specs/2026-05-24-qw2-design-v2.md`.

**Architecture:** QW-2 fetches directly from TLDV/Trello/GitHub RAW APIs, applies quality filters (DONE cards, low confidence, short text), runs inference routing to topic files, and writes decisions directly with dedupe + write-log rollback. QW-3 handles DM review for ambiguous decisions (confidence < 0.85) and routing failures. First run is always dry-run requiring explicit confirmation.

**Tech Stack:** Python 3, existing `vault/research/{tldv_client,trello_client,github_client}.py`, Telegram API via `message` tool, `ruff`+`mypy`+`pytest`.

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
  filter.py           # Quality filters (DONE, length, confidence)
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
  .confirmed            # flag: runs subsequentes escrevem
  .pending_confirmation/ # dry-run output awaiting confirm

tests/qw2/
  test_filter.py         # Parametrize table: DONE variants, length, confidence
  test_router.py         # Routing rules
  test_writer.py         # Append + dedupe + write log
  test_cursor.py         # Cursor read/write
  test_e2e.py            # Dry-run E2E with fixtures
  fixtures/
    tldv_meeting_with_decisions.json
    trello_card_done.json
    trello_card_decision.json
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
from vault.qw2.filter import should_skip, DONE_CARD_RE

@pytest.mark.parametrize("text,expected_skip,reason", [
    # DONE card variants
    ("Card 'X' foi concluído.\n\nLista: DONE", True, "standard DONE pattern"),
    ("Card 'X' foi concluída.\n\nLista: Done", True, "capitalisation variant"),
    ("foi concluído.\n\nLista:", True, "minimal DONE pattern"),
    ("Card 'X' foi concluído.\n\nLista:;", True, "semicolon variant"),
    ("Card 'X' foi concluído.\nLista:", False, "no newline before lista — not DONE format"),
    ("foi decidido que...", False, "real decision — not DONE"),
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
    # Edge: not a dict
    ("x" * 50, False, "string text OK with default confidence"),
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

import re
from typing import Any

DONE_CARD_RE = re.compile(
    r"foi conclu[ií]d[oa].*\nlista\s*:",
    re.IGNORECASE | re.DOTALL
)

def should_skip(claim: dict[str, Any]) -> tuple[bool, str]:
    """Return (skip, reason). False = process this claim."""
    text = claim.get("text", "")

    # 1. DONE card notifications
    if DONE_CARD_RE.search(text):
        return True, "Trello DONE card"

    # 2. Texto curto demais
    if len(text) < 50:
        return True, f"text too short ({len(text)} chars)"

    # 3. Confiança baixa
    confidence = claim.get("confidence", 0)
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
git commit -m "feat(qw2): quality filters — DONE regex, length, confidence"
```

---

## Task 3: `vault/qw2/cursor.py` — Per-Source Cursor Management

**Files:**
- Create: `vault/qw2/cursor.py`
- Modify: `tests/qw2/test_cursor.py` (new)

- [ ] **Step 1: Write failing test**

```python
# tests/qw2/test_cursor.py
import json, tempfile, Path
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
- Modify: `tests/qw2/test_dedupe.py` (new)

**Reference:** Spec sections 3.4 and 3.5.

- [ ] **Step 1: Write failing test**

```python
# tests/qw2/test_writer.py
import json, tempfile, Path
from vault.qw2.writer import QWWriter, load_written_refs, add_to_written_refs

def test_write_append_and_log(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("vault.qw2.writer.QW2_BASE", tmp_path)
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

def test_dedupe_no_rewrite(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("vault.qw2.writer.QW2_BASE", tmp_path)
    decision = {"text": "Teste", "source_ref": "tldv:meeting_abc", "confidence": 0.9,
                "date": "2026-05-24", "source": "tldv", "tags": []}
    writer = QWWriter()
    topic = tmp_path / "decisions" / "test.md"
    writer.write(topic, decision)
    writer.write(topic, decision)  # second write
    content = topic.read_text()
    # Should only appear once
    assert content.count("Teste") == 1
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
DECISIONS_DIR = Path("memory/curated")

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

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/writer.py tests/qw2/test_writer.py
git commit -m "feat(qw2): writer with dedupe and write log"
```

---

## Task 5: `vault/qw2/router.py` — Inference Pass

**Files:**
- Create: `vault/qw2/router.py`
- Create: `tests/qw2/test_router.py`

**Reference:** Spec section 3.3.

- [ ] **Step 1: Write failing test**

```python
# tests/qw2/test_router.py
import pytest
from vault.qw2.router import route_decision

@pytest.mark.parametrize("source,text,expected_topic", [
    ("tldv", "Status BAT reunião sobre erros", "bat-conectabot-observability.md"),
    ("tldv", "Discussão sobre TLDV e memory agent", "livy-memory-agent.md"),
    ("tldv", "Projeto Forge plataforma nova", "forge-platform.md"),
    ("trello", "Card sobre Delphos vistoria", "delphos-video-vistoria.md"),
    ("github", "PR sobre Evo sistema", "livy-evo.md"),
    ("tldv", "Algo que não matches", "general.md"),  # fallback → DM
    ("tldv", "Assunto sobre Kaba", "bat-conectabot-observability.md"),
])
def test_route_decision(source, text, expected_topic):
    result = route_decision({"text": text, "source": source})
    assert result["topic"] == expected_topic
    # routing_failed should be True only for general.md
    assert result.get("routing_failed") == (expected_topic == "general.md")
```

Run: `pytest tests/qw2/test_router.py -v`
Expected: FAIL

- [ ] **Step 2: Write implementation**

```python
# vault/qw2/router.py
"""Inference pass: map a decision to a topic file."""
from __future__ import annotations

import re
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

def route_decision(decision: dict[str, Any]) -> dict[str, Any]:
    """Route a decision to a topic file. Returns dict with topic, routing_failed."""
    text_lower = decision.get("text", "").lower()
    source_ref = decision.get("source_ref", "").lower()

    # Combine text + source_ref for matching
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
git commit -m "feat(qw2): inference pass router"
```

---

## Task 6: `vault/qw2/fetch_tldv.py` — TLDV Decision Extraction

**Files:**
- Create: `vault/qw2/fetch_tldv.py`
- Modify: `tests/qw2/test_fetch_tldv.py` (new)
- Reference: `vault/research/tldv_client.py`

**Reference:** Spec sections 3.2 (TLDV) and 5 (TLDV cursor details).

- [ ] **Step 1: Write implementation using existing TLDVClient**

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

def fetch_tldv_decisions(since_days: int = 7) -> list[dict[str, Any]]:
    """
    Fetch meetings updated in last N days, extract decisions.
    Returns list of decision dicts with: text, source_ref, confidence, date, source, tags.
    """
    client = TLDVClient(lookback_days=since_days)
    meetings = client.fetch_updated_meetings()

    decisions = []
    for meeting in meetings:
        name = meeting.get("name", "")
        meeting_id = meeting.get("id", "")

        # Skip Status meetings unless high confidence override (handled downstream)
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

    return decisions

def _meeting_date(meeting: dict) -> str:
    try:
        dt = datetime.fromisoformat(meeting.get("created_at", "").replace("Z", "+00:00"))
        return (dt - timedelta(hours=3)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

- [ ] **Step 2: Test with dry-run (no real API call needed in unit test — mock TLDVClient)**

```python
# tests/qw2/test_fetch_tldv.py
from unittest.mock import patch, MagicMock
from vault.qw2.fetch_tldv import fetch_tldv_decisions

@patch("vault.qw2.fetch_tldv.TLDVClient")
def test_fetch_tldv_extracts_decisions(mock_client_cls):
    mock_client = MagicMock()
    mock_client.fetch_updated_meetings.return_value = [
        {"id": "m1", "name": "Daily Bot", "created_at": "2026-05-24T12:00:00Z"}
    ]
    mock_client.fetch_meeting.return_value = {
        "summaries": [{"decisions": ["Usar GPT-4"], "tags": ["llm"]}]
    }
    mock_client_cls.return_value = mock_client

    results = fetch_tldv_decisions(since_days=7)
    assert len(results) == 1
    assert results[0]["text"] == "Usar GPT-4"
    assert results[0]["source_ref"] == "tldv:m1"
```

Run: `pytest tests/qw2/test_fetch_tldv.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/fetch_tldv.py tests/qw2/test_fetch_tldv.py
git commit -m "feat(qw2): TLDV decision fetcher"
```

---

## Task 7: `vault/qw2/fetch_trello.py` — Trello Decision Extraction

**Files:**
- Create: `vault/qw2/fetch_trello.py`
- Create: `tests/qw2/test_fetch_trello.py`
- Reference: `vault/research/trello_client.py`

**Reference:** Spec sections 3.2 (Trello board allowlist) and 6 (Trello cursor per board).

- [ ] **Step 1: Write implementation**

```python
# vault/qw2/fetch_trello.py
"""Fetch decisions from Trello cards."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from vault.research.trello_client import TrelloClient

logger = logging.getLogger(__name__)

ALLOWED_BOARDS = {
    "BAT", "Delphos", "Forge", "KABA", "4D Imobi", "Hydra", "Living",
}

def fetch_trello_decisions(since_days: int = 7) -> list[dict[str, Any]]:
    """
    Fetch cards from allowed boards updated in last N days.
    Extract decisions from card descriptions.
    """
    try:
        client = TrelloClient()
    except EnvironmentError as e:
        logger.warning(f"Trello not configured: {e}")
        return []

    all_cards = []
    for board in client.list_boards():
        board_name = board.get("name", "")
        if board_name not in ALLOWED_BOARDS:
            continue
        try:
            cards = client.get_board_cards(board["id"])
        except Exception as e:
            logger.warning(f"Error fetching board {board_name}: {e}")
            continue

        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)
        for card in cards:
            try:
                updated = datetime.fromisoformat(
                    card.get("dateLastUpdate", "").replace("Z", "+00:00")
                )
                if updated < cutoff:
                    continue
            except Exception:
                continue

            card["_board_name"] = board_name
            all_cards.append(card)

    decisions = []
    for card in all_cards:
        desc = card.get("desc", "") or ""
        if not desc or len(desc) < 50:
            continue
        decisions.append({
            "text": desc[:500],  # truncate for routing
            "source_ref": f"trello:{card.get('id', '')}",
            "confidence": 0.0,  # Trello cards: no LLM confidence
            "date": _card_date(card),
            "source": "trello",
            "card_name": card.get("name", ""),
            "board_name": card.get("_board_name", ""),
            "tags": [],
        })
    return decisions

def _card_date(card: dict) -> str:
    try:
        dt = datetime.fromisoformat(card.get("dateLastUpdate", "").replace("Z", "+00:00"))
        return (dt - timedelta(hours=3)).strftime("%Y-%m-%d")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")
```

- [ ] **Step 2: Write tests (mock TrelloClient)**

```python
# tests/qw2/test_fetch_trello.py
from unittest.mock import patch, MagicMock
from vault.qw2.fetch_trello import fetch_trello_decisions, ALLOWED_BOARDS

@patch("vault.qw2.fetch_trello.TrelloClient")
def test_fetches_only_allowed_boards(mock_client_cls):
    mock_client = MagicMock()
    mock_client.list_boards.return_value = [
        {"id": "b1", "name": "BAT"},
        {"id": "b2", "name": "Alexandre"},  # not allowed
    ]
    mock_client.get_board_cards.side_effect = [
        [{"id": "c1", "name": "Card 1", "desc": "Long desc " * 20,
          "dateLastUpdate": "2026-05-24T12:00:00Z"}],
        [],  # Alexandre board returns nothing (not allowed anyway)
    ]
    mock_client_cls.return_value = mock_client

    results = fetch_trello_decisions(since_days=7)
    assert len(results) == 1
    assert results[0]["board_name"] == "BAT"
    assert results[0]["source_ref"] == "trello:c1"
```

Run: `pytest tests/qw2/test_fetch_trello.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/fetch_trello.py tests/qw2/test_fetch_trello.py
git commit -m "feat(qw2): Trello decision fetcher with board allowlist"
```

---

## Task 8: `vault/qw2/fetch_github.py` — GitHub Decision Extraction

**Files:**
- Create: `vault/qw2/fetch_github.py`
- Create: `tests/qw2/test_fetch_github.py`
- Reference: `vault/research/github_client.py`

**Reference:** Spec section 6 (GitHub cursor).

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

def fetch_github_decisions(since_days: int = 7) -> list[dict[str, Any]]:
    """
    Fetch merged PRs from all living org repos since cursor.
    Extract decisions from PR titles and bodies.
    """
    try:
        client = GitHubClient(lookback_days=since_days)
    except EnvironmentError as e:
        logger.warning(f"GitHub not configured: {e}")
        return []

    events = client.fetch_events_since(None)
    decisions = []

    for event in events:
        pr = event.get("payload", {})
        title = pr.get("title", "")
        body = pr.get("body", "") or ""
        merged_at = pr.get("merged_at", "")
        url = pr.get("url", "")
        repo = event.get("repo", "")

        combined = f"{title} {body}".strip()
        if len(combined) < 50:
            continue

        decisions.append({
            "text": combined[:500],
            "source_ref": f"github:{repo}#{pr.get('number', '')}",
            "confidence": 0.85,  # GitHub PRs have moderate confidence
            "date": _pr_date(merged_at),
            "source": "github",
            "pr_title": title,
            "tags": [repo.split("/")[-1]] if repo else [],
            "url": url,
        })

    return decisions

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

    results = fetch_github_decisions(since_days=7)
    assert len(results) == 1
    assert results[0]["source_ref"] == "github:living/livy-memory-bot#42"
```

Run: `pytest tests/qw2/test_fetch_github.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add vault/qw2/fetch_github.py tests/qw2/test_fetch_github.py
git commit -m "feat(qw2): GitHub decision fetcher"
```

---

## Task 9: `vault/qw2/run.py` — Main CLI Entry Point

**Files:**
- Create: `vault/qw2/run.py`
- Modify: `vault/qw2/__init__.py`

**Reference:** Spec sections 6 (CLI) and 7 (File Structure).

- [ ] **Step 1: Write run.py**

```python
#!/usr/bin/env python3
"""QW-2 CLI: RAW → Topic Files pipeline."""
import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from vault.qw2 import fetch_tldv, fetch_trello, fetch_github
from vault.qw2.filter import should_skip
from vault.qw2.router import route_decision
from vault.qw2.writer import QWWriter
from vault.qw2.cursor import QWCursor
from vault.qw2 import rollback

QW2_BASE = Path(".research/qw2")
QW2_BASE.mkdir(parents=True, exist_ok=True)
DECISIONS_DIR = Path("memory/curated")
CONFIRMED_FLAG = QW2_BASE / ".confirmed"
PENDING_CONFIRM = QW2_BASE / ".pending_confirmation"

def is_confirmed() -> bool:
    return CONFIRMED_FLAG.exists()

def confirm_run() -> None:
    CONFIRMED_FLAG.parent.mkdir(parents=True, exist_ok=True)
    CONFIRMED_FLAG.touch()

def run(source: str = "all", dry_run: bool = True, since_days: int = 7) -> dict:
    summary = {"processed": 0, "written": 0, "skipped_dedupe": 0, "skipped_filter": 0,
               "errors": 0, "routing_failed": 0, "dm_candidates": []}

    # Always dry-run unless confirmed
    actual_dry_run = dry_run or not is_confirmed()
    if actual_dry_run:
        print("[QW-2] DRY-RUN — no writes")

    # Fetch decisions per source
    if source in ("tldv", "all"):
        decisions = fetch_tldv.fetch_tldv_decisions(since_days)
        _process_source("tldv", decisions, actual_dry_run, summary)

    if source in ("trello", "all"):
        decisions = fetch_trello.fetch_trello_decisions(since_days)
        _process_source("trello", decisions, actual_dry_run, summary)

    if source in ("github", "all"):
        decisions = fetch_github.fetch_github_decisions(since_days)
        _process_source("github", decisions, actual_dry_run, summary)

    # Update cursor per source
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    for s in ("tldv", "trello", "github"):
        if source in (s, "all"):
            QWCursor(s).write(now)

    # If dry-run results exist, DM Lincoln
    if actual_dry_run and summary["processed"] > 0:
        _send_dry_run_dm(summary)

    return summary

def _process_source(source: str, decisions: list, dry_run: bool, summary: dict) -> None:
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
            summary["routing_failed"] += 1
            summary["dm_candidates"].append(decision)
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

def _send_dry_run_dm(summary: dict) -> None:
    from message import message
    text = f"""🔍 QW-2 dry-run result

Processed: {summary['processed')}
Written: {summary['written']} | Skipped (dedupe): {summary['skipped_dedupe']} | Skipped (filter): {summary['skipped_filter']}
Routing failed (→ DM): {summary['routing_failed']}

[✅ Confirmar — proximo run escreve] [❌ Cancelar]
"""
    message(action="send", channel="telegram", target="7426291192", message=text)

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
Expected: runs without error (may return empty if no TLDV API key)

- [ ] **Step 2: Commit**

```bash
git add vault/qw2/run.py
git commit -m "feat(qw2): main CLI entry point with dry-run and confirm-run"
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
import argparse
import json
import sys
from pathlib import Path

QW2_BASE = Path(".research/qw2")
WRITE_LOG = QW2_BASE / "write_log.jsonl"
DECISIONS_DIR = Path("memory/curated")

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
        # Truncate log
        with open(WRITE_LOG, "w") as f:
            for entry in entries[:-n]:
                f.write(json.dumps(entry) + "\n")

def _remove_last_entry(topic: Path, source_ref: str) -> None:
    content = topic.read_text()
    # Simple approach: split on the source_ref marker and remove the preceding entry
    # This is approximate — for production, store entry boundaries
    lines = content.split("\n")
    # Find and remove the block starting with "### ...source_ref..."
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
from typing import Literal

QW2_BASE = Path(".research/qw2")
CONFIRMED_FLAG = QW2_BASE / ".confirmed"
PENDING_DIR = Path("memory/vault/pending")
ARCHIVE_DIR = PENDING_DIR / "archive"

def is_confirmed() -> bool:
    return CONFIRMED_FLAG.exists()

def is_rejected(claim_id: str) -> bool:
    return (ARCHIVE_DIR / f"{claim_id}.json").exists()

def handle_confirm(claim_id: str | None = None) -> str:
    """Mark run as confirmed. Idempotent."""
    if is_confirmed():
        return "already_confirmed"
    CONFIRMED_FLAG.parent.mkdir(parents=True, exist_ok=True)
    CONFIRMED_FLAG.touch()
    return "confirmed"

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

## Task 12: `vault/qw3/pending_dm.py` — DM for Low-Confidence Decisions

**Files:**
- Create: `vault/qw3/pending_dm.py`
- Create: `tests/qw3/test_pending_dm.py`

**Reference:** Spec sections 4.1 and 4.4 (DM format).

- [ ] **Step 1: Write implementation**

```python
# vault/qw3/pending_dm.py
"""QW-3: DM Lincoln for low-confidence decisions and routing failures."""
from __future__ import annotations

import json
from pathlib import Path

PENDING_DIR = Path("memory/vault/pending")
LINCOLN_ID = "7426291192"

def send_pending_dm(decisions: list[dict]) -> None:
    """Send DM listing pending decisions awaiting approval."""
    if not decisions:
        return
    from message import message
    lines = [f"🔍 QW-2 result — pending confirmation\n\nDecisões geradas: {len(decisions)}\n"]
    for d in decisions:
        conf = d.get("confidence", 0)
        text = d.get("text", "")[:80]
        topic = d.get("topic", "unknown")
        lines.append(f"• [{d.get('source', '?').upper()}] {text} → {topic} (conf: {conf:.0%})")
    text = "\n".join(lines)
    text += "\n\n[✅ Confirmar — proximo run escreve] [❌ Cancelar]"
    message(action="send", channel="telegram", target=LINCOLN_ID, message=text)

def save_pending(decision: dict) -> Path:
    """Save a pending decision to pending/ directory."""
    claim_id = decision.get("source_ref", "").replace(":", "_")
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    path = PENDING_DIR / f"{claim_id}.json"
    path.write_text(json.dumps(decision, indent=2))
    return path
```

- [ ] **Step 2: Commit**

```bash
git add vault/qw3/pending_dm.py tests/qw3/test_pending_dm.py
git commit -m "feat(qw3): pending DM sender"
```

---

## Task 13: End-to-End Tests + Quality Gates

**Files:**
- Modify: `tests/qw2/test_e2e.py` (new)
- Add: `tests/qw2/fixtures/tldv_meeting_with_decisions.json` (sample fixture)

**Reference:** Spec section 9 (Quality Gates).

- [ ] **Step 1: Write E2E dry-run test**

```python
# tests/qw2/test_e2e.py
"""QW-2 E2E dry-run tests with fixtures."""
import json, pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

# Fixture: TLDV meeting with decisions
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
```

- [ ] **Step 2: Create fixture file**

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
git commit -m "test(qw2 qw3): E2E dry-run tests and fixtures"
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
  --payload '{"kind":"agentTurn","message":"Run QW-2: cd /home/lincoln/.openclaw/workspace-livy-memory && python vault/qw2/run.py --source all --days 7"}' \
  --delivery '{"mode":"announce","channel":"telegram","to":"7426291192"}'

# QW-2 weekly dry-run (domingo) — validate before real runs
openclaw cron add \
  --name "qw2-dry-run-weekly" \
  --schedule '{"kind":"cron","expr":"0 7 * * 0","tz":"America/Sao_Paulo"}' \
  --sessionTarget "isolated" \
  --payload '{"kind":"agentTurn","message":"Run QW-2 dry-run: cd /home/lincoln/.openclaw/workspace-livy-memory && python vault/qw2/run.py --dry-run --source all --days 7"}' \
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
✅ Quality filters: DONE card regex + length + confidence
✅ Board allowlist: 7 boards Living
✅ Dedupe: written_refs.json + write_log.jsonl
✅ Dry-run first run + DM confirmation
```

- [ ] **Step 2: Commit**

```bash
git add HEARTBEAT.md
git commit -m "docs: HEARTBEAT — QW-2 + QW-3 operational"
```

---

## Implementation Order

1. **Task 1** — Project scaffolding
2. **Task 2** — `filter.py` + tests (foundation of everything)
3. **Task 3** — `cursor.py` + tests
4. **Task 4** — `writer.py` + tests (depends on filter)
5. **Task 5** — `router.py` + tests
6. **Task 6** — `fetch_tldv.py` + tests
7. **Task 7** — `fetch_trello.py` + tests
8. **Task 8** — `fetch_github.py` + tests
9. **Task 9** — `run.py` (integrates all above)
10. **Task 10** — `rollback.py`
11. **Task 11** — `callbacks.py` (QW-3)
12. **Task 12** — `pending_dm.py` (QW-3)
13. **Task 13** — E2E tests + lint + mypy
14. **Task 14** — Register cron jobs
15. **Task 15** — Update HEARTBEAT.md
