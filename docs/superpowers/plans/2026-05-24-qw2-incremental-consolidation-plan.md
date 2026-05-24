# QW-2 — Consolidação Incremental + Honcho + Fact-Check Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar consolidação incremental, Honcho indexing e fact-check ao pipeline QW-2.

**Architecture:** Eventually consistent — QW-2 (fetch+write) → consolidate.py (dedupe+fact-check) → honcho_indexer.py (index to Honcho). Lock partilhado por todos os módulos.

**Tech Stack:** Python 3, vault/fact_check.py (existing), Honcho API (HTTP), pathlib

---

## File Structure

```
vault/qw2/
├── lock.py              # NOVO: lock partilhado (create)
├── fact_check.py        # NOVO: wrapper (create)
├── consolidate.py       # NOVO: dedupe + fact-check (create)
├── honcho_indexer.py    # NOVO: Honcho indexing (create)
├── run.py              # MODIFY: add --reset flags + lock
└── rollback.py          # EXISTING: keep as-is

tests/qw2/
├── test_consolidate.py       # NOVO (create)
├── test_honcho_indexer.py    # NOVO (create)
├── test_lock.py             # NOVO (create)
├── test_fact_check.py       # NOVO (create)
└── test_reset_flags.py       # NOVO (create)
```

---

## Task 1: `vault/qw2/lock.py` — Módulo de Lock Partilhado

**Files:**
- Create: `vault/qw2/lock.py`
- Test: `tests/qw2/test_lock.py`

- [ ] **Step 1: Criar lock.py com API mínima**

```python
# vault/qw2/lock.py
from pathlib import Path
import time
import os
import uuid

LOCK_FILE = Path(".research/qw2/.qw2.lock")
LOCK_TTL_SECONDS = 600

def _lock_pid() -> str:
    return f"{os.getpid()}|{uuid.uuid4().hex[:8]}"

def acquire_lock() -> bool:
    """Cria lock file. Retorna True se adquirido, False s e lock existe e é fresco."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        try:
            pid, ts = LOCK_FILE.read_text().split("|")
            age = time.time() - float(ts)
            if age < LOCK_TTL_SECONDS:
                return False  # lock fresco, não sobrescrever
        except Exception:
            pass  # lock corrupto, sobrescrever
    LOCK_FILE.write_text(f"{_lock_pid()}|{time.time()}")
    return True

def release_lock() -> bool:
    """Remove lock file. Retorna True se removido, False se não era o lock actual."""
    if not LOCK_FILE.exists():
        return True
    try:
        pid, _ = LOCK_FILE.read_text().split("|")
        if pid != str(os.getpid()):
            return False  # não é o nosso lock
        LOCK_FILE.unlink()
        return True
    except Exception:
        return False

def is_locked() -> bool:
    """Check se lock existe e não é stale."""
    if not LOCK_FILE.exists():
        return False
    try:
        _, ts = LOCK_FILE.read_text().split("|")
        age = time.time() - float(ts)
        return age < LOCK_TTL_SECONDS
    except Exception:
        return False
```

- [ ] **Step 2: Criar teste para lock**

```python
# tests/qw2/test_lock.py
import pytest
import time
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))
from vault.qw2.lock import acquire_lock, release_lock, is_locked, LOCK_FILE

def test_acquire_lock_succeeds_when_no_lock():
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
    result = acquire_lock()
    assert result is True
    assert LOCK_FILE.exists()
    release_lock()

def test_acquire_lock_fails_when_fresh_lock_exists():
    acquire_lock()  # cria lock
    result = acquire_lock()
    assert result is False
    release_lock()

def test_acquire_lock_succeeds_when_stale_lock():
    acquire_lock()
    # simular lock stale: escrever timestamp antigo
    LOCK_FILE.write_text(f"9999|{time.time() - 700}")
    result = acquire_lock()
    assert result is True
    release_lock()

def test_release_lock_removes_file():
    acquire_lock()
    result = release_lock()
    assert result is True
    assert not LOCK_FILE.exists()

def test_is_locked_true_when_fresh():
    acquire_lock()
    assert is_locked() is True
    release_lock()

def test_is_locked_false_when_no_lock():
    if LOCK_FILE.exists():
        release_lock()
    assert is_locked() is False
```

- [ ] **Step 3: Run tests**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && PYTHONPATH=. pytest tests/qw2/test_lock.py -v`

Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add vault/qw2/lock.py tests/qw2/test_lock.py
git commit -m "feat(qw2): shared lock module with TTL"
```

---

## Task 2: `vault/qw2/fact_check.py` — Wrapper Fact-Check

**Files:**
- Create: `vault/qw2/fact_check.py`
- Test: `tests/qw2/test_fact_check.py`

- [ ] **Step 1: Criar wrapper que usa vault/fact_check.py**

```python
# vault/qw2/fact_check.py
"""
QW-2 fact-check wrapper.
Usa vault/fact_check.score_confidence() para calcular confidence_level.
"""
from __future__ import annotations

from typing import Any, TypedDict

# Import from vault library
import sys
from pathlib import Path as _Path

_WS = _Path(__file__).resolve().parents[2]
if str(_WS) not in sys.path:
    sys.path.insert(0, str(_WS))

from vault.fact_check import score_confidence


class Decision(TypedDict):
    source: str  # tldv | github | trello
    source_ref: str
    confidence_level: str | None
    corroborated_sources: list[str] | None


def enrich_decision(decision: Decision) -> dict[str, Any]:
    """
    Recebe decision dict com 'source' (tldv/github/trello).
    Retorna decision com 'confidence_level' adicionado.

    Mapping:
    - tldv  → official+=1
    - github → official+=1
    - trello → indirect+=1
    - corroborated_sources (list) → corroborated += len(list)
    """
    if decision.get("confidence_level"):
        return decision  # skip se já calculado

    source = decision.get("source", "")
    official = 0
    corroborated = 0
    indirect = 0

    if source == "tldv":
        official += 1
    elif source == "github":
        official += 1
    elif source == "trello":
        indirect += 1

    # corroborated sources elevam o nível
    corrob = decision.get("corroborated_sources") or []
    corroborated = len(corrob)

    level = score_confidence(official, corroborated, indirect)
    decision["confidence_level"] = level
    return decision


def enrich_decisions(decisions: list[Decision]) -> list[Decision]:
    """Batch version of enrich_decision."""
    return [enrich_decision(d) for d in decisions]
```

- [ ] **Step 2: Criar teste para fact_check wrapper**

```python
# tests/qw2/test_fact_check.py
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))
from vault.qw2.fact_check import enrich_decision, enrich_decisions

def test_tldv_decision_medium():
    d = {"source": "tldv", "source_ref": "tldv:abc", "confidence_level": None, "corroborated_sources": None}
    result = enrich_decision(d)
    assert result["confidence_level"] == "medium"

def test_github_decision_medium():
    d = {"source": "github", "source_ref": "github:xyz", "confidence_level": None, "corroborated_sources": None}
    result = enrich_decision(d)
    assert result["confidence_level"] == "medium"

def test_trello_decision_low():
    d = {"source": "trello", "source_ref": "trello:xyz", "confidence_level": None, "corroborated_sources": None}
    result = enrich_decision(d)
    assert result["confidence_level"] == "low"

def test_tldv_with_corroborated_high():
    d = {"source": "tldv", "source_ref": "tldv:abc", "confidence_level": None, "corroborated_sources": ["github:xyz"]}
    result = enrich_decision(d)
    assert result["confidence_level"] == "high"

def test_skips_if_already_has_confidence_level():
    d = {"source": "tldv", "source_ref": "tldv:abc", "confidence_level": "high", "corroborated_sources": None}
    result = enrich_decision(d)
    assert result["confidence_level"] == "high"  # não recalcula

def test_enrich_decisions_batch():
    decisions = [
        {"source": "tldv", "source_ref": "tldv:a", "confidence_level": None, "corroborated_sources": None},
        {"source": "trello", "source_ref": "trello:b", "confidence_level": None, "corroborated_sources": None},
    ]
    results = enrich_decisions(decisions)
    assert results[0]["confidence_level"] == "medium"
    assert results[1]["confidence_level"] == "low"
```

- [ ] **Step 3: Run tests**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && PYTHONPATH=. pytest tests/qw2/test_fact_check.py -v`

Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add vault/qw2/fact_check.py tests/qw2/test_fact_check.py
git commit -m "feat(qw2): fact_check wrapper for score_confidence"
```

---

## Task 3: `vault/qw2/consolidate.py` — Dedupe + Fact-Check

**Files:**
- Create: `vault/qw2/consolidate.py`
- Test: `tests/qw2/test_consolidate.py`

- [ ] **Step 1: Criar consolidate.py**

```python
# vault/qw2/consolidate.py
"""
consolidate.py — Dedupe intra-file + fact-check enrichment.
Runs after QW-2 writes to topic files.
"""
from __future__ import annotations

import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TypedDict

_WS = Path(__file__).resolve().parents[2]
if str(_WS) not in sys.path:
    sys.path.insert(0, str(_WS))

from vault.qw2.lock import acquire_lock, release_lock
from vault.qw2.fact_check import enrich_decision

DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"

# Entry regex: capture date, source, text, source_ref, confidence, tags
ENTRY_RE = re.compile(
    r"\n### (\d{4}-\d{2}-\d{2}) — (\w+)\n> (.+?)\n- \*\*Source\*\*: (.+?)\n- \*\*Confidence\*\*: (.+?)\n",
    re.DOTALL,
)

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


class ParsedEntry(TypedDict):
    date: str
    source: str
    text: str
    source_ref: str
    confidence: str
    tags: str
    confidence_level: str | None


def parse_topic_file(path: Path) -> list[ParsedEntry]:
    """Parse all entries from a topic file. Returns list of ParsedEntry."""
    content = path.read_text()
    entries: list[ParsedEntry] = []

    # Extract frontmatter if present
    fm_match = FRONTMATTER_RE.match(content)
    frontmatter: dict[str, str] = {}
    if fm_match:
        for line in fm_match.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                frontmatter[k.strip()] = v.strip()

    body = FRONTMATTER_RE.sub("", content)

    for match in ENTRY_RE.finditer(body):
        entry: ParsedEntry = {
            "date": match.group(1),
            "source": match.group(2),
            "text": match.group(3).strip(),
            "source_ref": match.group(4).strip(),
            "confidence": match.group(5).strip(),
            "tags": "",
            "confidence_level": frontmatter.get("confidence_level"),
        }
        entries.append(entry)

    return entries


def dedupe_entries(entries: list[ParsedEntry]) -> list[ParsedEntry]:
    """Remove duplicate source_refs, keeping latest by date."""
    seen: dict[str, ParsedEntry] = {}
    for entry in entries:
        ref = entry["source_ref"]
        if ref not in seen or entry["date"] > seen[ref]["date"]:
            seen[ref] = entry
    return list(seen.values())


def build_frontmatter(topic_name: str, confidence_level: str | None = None) -> str:
    """Build YAML frontmatter string."""
    lines = ["---", f"name: {topic_name}"]
    if confidence_level:
        lines.append(f"confidence_level: {confidence_level}")
    lines.append("---")
    return "\n".join(lines) + "\n"


def rewrite_topic_file(path: Path, entries: list[ParsedEntry], topic_name: str) -> None:
    """Rewrite topic file with deduplicated + enriched entries."""
    # Sort by date descending
    entries_sorted = sorted(entries, key=lambda e: e["date"], reverse=True)

    # Build new content
    lines = [build_frontmatter(topic_name)]
    for e in entries_sorted:
        level = e.get("confidence_level") or ""
        lines.append(f"### {e['date']} — {e['source']}\n")
        lines.append(f"> {e['text']}\n")
        lines.append(f"- **Source:** {e['source_ref']}\n")
        lines.append(f"- **Confidence:** {e['confidence']}\n")
        if level:
            lines.append(f"- **Confidence Level:** {level}\n")

    path.write_text("\n".join(lines))


def consolidate_topic(path: Path, dry_run: bool = False) -> dict[str, int]:
    """Consolidate a single topic file. Returns stats dict."""
    topic_name = path.stem
    entries = parse_topic_file(path)
    total = len(entries)

    deduped = dedupe_entries(entries)
    removed = total - len(deduped)

    # Fact-check: enrich each entry (adds confidence_level)
    enriched = [enrich_decision(dict(e)) for e in deduped]

    if not dry_run:
        rewrite_topic_file(path, enriched, topic_name)

    return {
        "processed": 1,
        "entries_total": total,
        "deduped": removed,
        "fact_checked": len(enriched),
        "written": 0 if dry_run else 1,
        "errors": 0,
    }


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="QW-2 Consolidate")
    parser.add_argument("--all", action="store_true", help="Consolidate all topic files")
    parser.add_argument("--topic", help="Consolidate specific topic file (without .md)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    parser.add_argument("--reset", action="store_true", help="Clear confidence_level from frontmatter")
    args = parser.parse_args()

    if not acquire_lock():
        print("ERROR: Lock file exists, another run in progress")
        sys.exit(1)

    try:
        if args.topic:
            topic_path = DECISIONS_DIR / f"{args.topic}.md"
            if not topic_path.exists():
                print(f"WARNING: {topic_path} not found")
                sys.exit(1)
            stats = consolidate_topic(topic_path, dry_run=args.dry_run)
            print(stats)
        elif args.all or args.reset:
            stats = {"processed": 0, "entries_total": 0, "deduped": 0, "fact_checked": 0, "written": 0, "errors": 0}
            for path in DECISIONS_DIR.glob("*.md"):
                if path.name == ".gitkeep":
                    continue
                s = consolidate_topic(path, dry_run=args.dry_run)
                for k in stats:
                    stats[k] += s[k]
            print(stats)
        else:
            print("Specify --all or --topic NAME")
            sys.exit(1)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Criar fixture e teste para consolidate**

```python
# tests/qw2/test_consolidate.py
import pytest
import tempfile
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))
from vault.qw2.consolidate import parse_topic_file, dedupe_entries, consolidate_topic

@pytest.fixture
def sample_topic_file(tmp_path):
    content = """---
name: test-topic
---

### 2026-05-07 — tldv
> SVD e Hidra seguem com integração via fila

- **Source:** tldv:abc123
- **Confidence:** 0.92

### 2026-05-07 — tldv
> SVD e Hidra seguem com integração via fila

- **Source:** tldv:abc123
- **Confidence:** 0.92

### 2026-05-06 — github
> Deploy de todos os serviços no Azure

- **Source:** github:xyz789
- **Confidence:** 0.85
"""
    p = tmp_path / "test-topic.md"
    p.write_text(content)
    return p

def test_parse_topic_file(sample_topic_file):
    entries = parse_topic_file(sample_topic_file)
    assert len(entries) == 3

def test_dedupe_keeps_latest(sample_topic_file):
    entries = parse_topic_file(sample_topic_file)
    deduped = dedupe_entries(entries)
    assert len(deduped) == 2  # 2 unique source_refs
    # tldv:abc123 appears twice (same date) → one wins
    # github:xyz789 → 1

def test_dedupe_different_source_refs_kept(sample_topic_file):
    entries = parse_topic_file(sample_topic_file)
    deduped = dedupe_entries(entries)
    refs = {e["source_ref"] for e in deduped}
    assert "tldv:abc123" in refs
    assert "github:xyz789" in refs

def test_consolidate_dry_run_no_modify(sample_topic_file):
    original = sample_topic_file.read_text()
    stats = consolidate_topic(sample_topic_file, dry_run=True)
    assert stats["deduped"] == 1
    assert stats["written"] == 0
    assert sample_topic_file.read_text() == original

def test_consolidate_writes_deduplicated(sample_topic_file):
    stats = consolidate_topic(sample_topic_file, dry_run=False)
    assert stats["deduped"] == 1
    assert stats["written"] == 1
    entries = parse_topic_file(sample_topic_file)
    assert len(entries) == 2
```

- [ ] **Step 3: Run tests**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && PYTHONPATH=. pytest tests/qw2/test_consolidate.py -v`

Expected: 5 passed

- [ ] **Step 4: Commit**

```bash
git add vault/qw2/consolidate.py tests/qw2/test_consolidate.py
git commit -m "feat(qw2): consolidate dedupe + fact-check"
```

---

## Task 4: `vault/qw2/honcho_indexer.py` — Honcho Indexing

**Files:**
- Create: `vault/qw2/honcho_indexer.py`
- Test: `tests/qw2/test_honcho_indexer.py`

- [ ] **Step 1: Criar honcho_indexer.py**

```python
# vault/qw2/honcho_indexer.py
"""
honcho_indexer.py — Index decisions to Honcho with supersedes chain.
"""
from __future__ import annotations

import httpx
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_WS = Path(__file__).resolve().parents[2]
if str(_WS) not in sys.path:
    sys.path.insert(0, str(_WS))

from vault.qw2.lock import acquire_lock, release_lock
from vault.qw2.consolidate import parse_topic_file

DECISIONS_DIR = _WS / "memory" / "vault" / "decisions"
HONCHO_BASE = "http://100.121.74.111:8000"
HONCHO_WORKSPACE = "openclaw"
HONCHO_AGENT_PEER = "agent-memory-agent"

# source_ref extraction: "tldv:abc" → source_type="tldv"
SOURCE_REF_RE = re.compile(r"^(tldv|github|trello):")

# Content extraction from conclusions list
CONCLUSION_CONTENT_RE = re.compile(r"source_ref:([^\s|]+)")


def get_source_type(source_ref: str) -> str:
    """Extract source type from source_ref prefix."""
    m = SOURCE_REF_RE.match(source_ref)
    return m.group(1) if m else "unknown"


def build_content(entry: dict[str, Any], supersedes: str | None = None) -> str:
    """Build pipe-delimited content string."""
    parts = [
        entry.get("date", ""),
        entry.get("text", "")[:200],
        entry.get("source_ref", ""),
        f"confidence:{entry.get('confidence_level', 'unverified')}",
        f"tags:{entry.get('tags', '')}",
    ]
    if supersedes:
        parts.append(f"supersedes:{supersedes}")
    return " | ".join(parts)


def find_existing_conclusion(source_ref: str, source_type: str) -> str | None:
    """
    Search Honcho for existing conclusion with same source_ref.
    Uses POST /conclusions/list with filters.
    Returns conclusion ID if found, None otherwise.
    """
    url = f"{HONCHO_BASE}/v3/workspaces/{HONCHO_WORKSPACE}/conclusions/list"
    headers = {"Content-Type": "application/json"}
    payload = {
        "filters": {"observed_id": source_type}
    }

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None
        data = resp.json()
        conclusions = data if isinstance(data, list) else data.get("conclusions", [])

        for c in conclusions:
            content = c.get("content", "")
            # Exact match: content contains source_ref as "source_ref:{value}"
            if f"source_ref:{source_ref}" in content or source_ref in content:
                return c.get("id")
    except Exception:
        pass
    return None


def index_decision(entry: dict[str, Any], dry_run: bool = False) -> dict[str, str]:
    """Index a single decision to Honcho. Returns result dict."""
    source_ref = entry.get("source_ref", "")
    source_type = get_source_type(source_ref)
    if not source_ref or source_type == "unknown":
        return {"status": "skipped", "reason": "no source_ref"}

    # Find existing conclusion
    existing_id = find_existing_conclusion(source_ref, source_type) if not dry_run else None

    supersedes = existing_id if existing_id else None
    content = build_content(entry, supersedes)

    if dry_run:
        return {
            "status": "would_index",
            "source_ref": source_ref,
            "supersedes": supersedes,
            "content": content[:100],
        }

    # POST to Honcho
    url = f"{HONCHO_BASE}/v3/workspaces/{HONCHO_WORKSPACE}/conclusions"
    payload = {
        "conclusions": [{
            "content": content,
            "observer_id": HONCHO_AGENT_PEER,
            "observed_id": source_type,
        }]
    }

    try:
        resp = httpx.post(url, json=payload, timeout=15)
        if resp.status_code == 201:
            new_id = resp.json()[0].get("id", "")
            return {"status": "indexed", "id": new_id, "superseded": existing_id}
        else:
            return {"status": "error", "code": resp.status_code, "body": resp.text[:100]}
    except Exception as e:
        return {"status": "error", "exception": str(e)}


def index_topic(path: Path, since: str | None = None, dry_run: bool = False) -> dict[str, int]:
    """Index all decisions from a topic file."""
    entries = parse_topic_file(path)
    stats = {"indexed": 0, "superseded": 0, "skipped": 0, "errors": 0}

    for entry in entries:
        if since and entry.get("date", "") < since:
            continue
        result = index_decision(entry, dry_run=dry_run)
        if result.get("status") == "indexed":
            stats["indexed"] += 1
            if result.get("superseded"):
                stats["superseded"] += 1
        elif result.get("status") == "skipped":
            stats["skipped"] += 1
        else:
            stats["errors"] += 1

    return stats


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="QW-2 Honcho Indexer")
    parser.add_argument("--all", action="store_true", help="Index all topic files")
    parser.add_argument("--since", help="Index only entries since DATE (ISO format)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be done")
    args = parser.parse_args()

    if not acquire_lock():
        print("ERROR: Lock file exists")
        sys.exit(1)

    try:
        stats = {"indexed": 0, "superseded": 0, "skipped": 0, "errors": 0}
        for path in DECISIONS_DIR.glob("*.md"):
            if path.name == ".gitkeep":
                continue
            s = index_topic(path, since=args.since, dry_run=args.dry_run)
            for k in stats:
                stats[k] += s[k]
        print(stats)
    finally:
        release_lock()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Criar teste para honcho_indexer (mock httpx)**

```python
# tests/qw2/test_honcho_indexer.py
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[3]))
from vault.qw2.honcho_indexer import get_source_type, build_content

def test_get_source_type_tldv():
    assert get_source_type("tldv:abc123") == "tldv"

def test_get_source_type_github():
    assert get_source_type("github:xyz789") == "github"

def test_get_source_type_trello():
    assert get_source_type("trello:card123") == "trello"

def test_get_source_type_unknown():
    assert get_source_type("unknown:ref") == "unknown"

def test_build_content_basic():
    entry = {
        "date": "2026-05-07",
        "text": "Deploy to Azure",
        "source_ref": "github:xyz789",
        "confidence_level": "high",
        "tags": "azure,deploy",
    }
    content = build_content(entry)
    assert "2026-05-07" in content
    assert "Deploy to Azure" in content
    assert "github:xyz789" in content
    assert "confidence:high" in content
    assert "tags:azure,deploy" in content

def test_build_content_with_supersedes():
    entry = {
        "date": "2026-05-07",
        "text": "Updated decision",
        "source_ref": "tldv:abc123",
        "confidence_level": "medium",
        "tags": "",
    }
    content = build_content(entry, supersedes="old_id_123")
    assert "supersedes:old_id_123" in content
```

- [ ] **Step 3: Run tests**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && PYTHONPATH=. pytest tests/qw2/test_honcho_indexer.py -v`

Expected: 6 passed

- [ ] **Step 4: Commit**

```bash
git add vault/qw2/honcho_indexer.py tests/qw2/test_honcho_indexer.py
git commit -m "feat(qw2): honcho indexer with supersedes chain"
```

---

## Task 5: `vault/qw2/run.py` — Reset Flags + Lock

**Files:**
- Modify: `vault/qw2/run.py`
- Test: `tests/qw2/test_reset_flags.py`

- [ ] **Step 1: Add lock to run.py**

Find the `def run()` function and add lock at the start and release at end:

```python
# Add near top of run():
# from vault.qw2.lock import acquire_lock, release_lock

# At start of run():
if not dry_run:
    if not acquire_lock():
        logger.warning("QW-2 already running, skipping")
        return {"skipped": "lock"}
```

At end of `run()` add:
```python
    finally:
        if not dry_run:
            release_lock()
```

- [ ] **Step 2: Add reset flags to run.py argument parser**

Find argparse section and add:

```python
parser.add_argument("--reset", action="store_true", help="Hard reset: clears cursors + written_refs + dedupe refs")
parser.add_argument("--reset-cursors", action="store_true", help="Clear only cursors (keep dedupe)")
parser.add_argument("--reset-dedupe", action="store_true", help="Clear only dedupe refs (keep cursors)")
parser.add_argument("--reset-tldv", action="store_true", help="Clear only TLDV cursor + dedupe")
parser.add_argument("--reset-github", action="store_true", help="Clear only GitHub cursor + dedupe")
parser.add_argument("--reset-trello", action="store_true", help="Clear only Trello cursor + dedupe")
```

- [ ] **Step 3: Implement reset logic**

After argument parsing, add before the main loop:

```python
RESEARCH_DIR = Path(".research/qw2")
CURSOR_FILES = {
    "tldv": RESEARCH_DIR / "last_seen_tldv.json",
    "github": RESEARCH_DIR / "last_seen_github.json",
    "trello": RESEARCH_DIR / "last_seen_trello.json",
}
WRITTEN_REFS = RESEARCH_DIR / "written_refs.json"
WRITE_LOG = RESEARCH_DIR / "write_log.jsonl"

def do_reset(which: set[str]) -> None:
    """Reset cursor files and/or dedupe files."""
    if "all" in which or "tldv" in which:
        (RESEARCH_DIR / "last_seen_tldv.json").unlink(missing_ok=True)
    if "all" in which or "github" in which:
        (RESEARCH_DIR / "last_seen_github.json").unlink(missing_ok=True)
    if "all" in which or "trello" in which:
        (RESEARCH_DIR / "last_seen_trello.json").unlink(missing_ok=True)
    if "all" in which or "dedupe" in which:
        WRITTEN_REFS.unlink(missing_ok=True)
        WRITE_LOG.unlink(missing_ok=True)
```

After argparse, add:

```python
    if args.reset:
        do_reset({"all"})
    elif args.reset_cursors:
        do_reset({"tldv", "github", "trello"})
    elif args.reset_dedupe:
        do_reset({"dedupe"})
    elif args.reset_tldv:
        do_reset({"tldv", "dedupe"})
    elif args.reset_github:
        do_reset({"github", "dedupe"})
    elif args.reset_trello:
        do_reset({"trello", "dedupe"})
```

- [ ] **Step 4: Run existing QW-2 tests**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && PYTHONPATH=. pytest tests/qw2/ -v --ignore=tests/qw2/test_reset_flags.py -q`

Expected: all existing tests pass

- [ ] **Step 5: Commit**

```bash
git add vault/qw2/run.py
git commit -m "feat(qw2): add --reset flags + lock to run.py"
```

---

## Task 6: Testes de Integração

**Files:**
- Create: `tests/qw2/test_reset_flags.py`

- [ ] **Step 1: Create integration tests for reset flags**

```python
# tests/qw2/test_reset_flags.py
import pytest
from pathlib import Path
import sys
import json
sys.path.insert(0, str(Path(__file__).parents[3]))

RESEARCH_DIR = Path(".research/qw2")
CURSOR_FILES = {
    "tldv": RESEARCH_DIR / "last_seen_tldv.json",
    "github": RESEARCH_DIR / "last_seen_github.json",
    "trello": RESEARCH_DIR / "last_seen_trello.json",
}
WRITTEN_REFS = RESEARCH_DIR / "written_refs.json"
WRITE_LOG = RESEARCH_DIR / "write_log.jsonl"

def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")

def _setup_all():
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    for p in CURSOR_FILES.values():
        _touch(p)
    _touch(WRITTEN_REFS)
    _touch(WRITE_LOG)

def _teardown():
    for p in CURSOR_FILES.values():
        p.unlink(missing_ok=True)
    WRITTEN_REFS.unlink(missing_ok=True)
    WRITE_LOG.unlink(missing_ok=True)

@pytest.fixture(autouse=True)
def setup_and_teardown():
    _setup_all()
    yield
    _teardown()

def test_reset_clears_all():
    from vault.qw2.run import do_reset
    do_reset({"all"})
    for p in CURSOR_FILES.values():
        assert not p.exists()
    assert not WRITTEN_REFS.exists()
    assert not WRITE_LOG.exists()

def test_reset_tldv_clears_only_tldv():
    from vault.qw2.run import do_reset
    do_reset({"tldv", "dedupe"})
    assert not CURSOR_FILES["tldv"].exists()
    assert CURSOR_FILES["github"].exists()
    assert CURSOR_FILES["trello"].exists()
    assert not WRITTEN_REFS.exists()

def test_reset_github_clears_only_github():
    from vault.qw2.run import do_reset
    do_reset({"github", "dedupe"})
    assert CURSOR_FILES["tldv"].exists()
    assert not CURSOR_FILES["github"].exists()
    assert CURSOR_FILES["trello"].exists()
    assert not WRITTEN_REFS.exists()

def test_reset_cursors_keeps_dedupe():
    from vault.qw2.run import do_reset
    do_reset({"tldv", "github", "trello"})
    assert not CURSOR_FILES["tldv"].exists()
    assert not CURSOR_FILES["github"].exists()
    assert not CURSOR_FILES["trello"].exists()
    assert WRITTEN_REFS.exists()
    assert WRITE_LOG.exists()
```

- [ ] **Step 2: Run tests**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && PYTHONPATH=. pytest tests/qw2/test_reset_flags.py -v`

Expected: 4 passed

- [ ] **Step 3: Commit**

```bash
git add tests/qw2/test_reset_flags.py
git commit -m "test(qw2): reset flags integration tests"
```

---

## Validation

After all tasks complete:

```bash
cd /home/lincoln/.openclaw/workspace-livy-memory

# All tests
PYTHONPATH=. pytest tests/qw2/ -q

# Dry-run consolidate on real data
python3 vault/qw2/consolidate.py --all --dry-run

# Dry-run honcho indexer
python3 vault/qw2/honcho_indexer.py --all --dry-run

# Verify lock works
python3 vault/qw2/run.py --source all --dry-run &
sleep 1
python3 vault/qw2/run.py --source all --dry-run  # should skip
```

---

## Quick Wins (Implement First)

1. **consolidate.py --dry-run** — valida dedupe sem modificar ficheiros
2. **honcho_indexer.py --dry-run** — mostra o que seria indexado
3. **lock.py** — segurança mínima antes de ligar ao cron
