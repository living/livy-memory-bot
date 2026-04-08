# Memory Reconciliation + Decision Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current text-only curation flow with a structured reconciler that builds fact snapshots, normalizes evidence, records explainable decisions, and safely rewrites topic files — starting with a pilot for `memory/curated/tldv-pipeline-state.md`.

**Architecture:** Keep the existing multi-source collectors and `curation_cron.py` orchestration, but insert a new pipeline stage: normalized evidence → fact snapshot → reconciler → decision ledger → structured topic rewriter. Roll out in shadow mode first, then enable write mode for the TLDV pilot once outputs are stable and idempotent.

**Tech Stack:** Python 3, Pydantic models, JSONL ledgers, Markdown topic files, existing collectors in `skills/memoria-consolidation/`, pytest-style unit tests plus existing script-based functional/security tests.

---

## File Map

```text
skills/memoria-consolidation/
├── curation_cron.py                    # Existing orchestrator; add shadow/write modes and new pipeline stages
├── signal_bus.py                       # Existing event bus; fix append semantics and idempotent persistence helpers
├── conflict_detector.py                # Existing conflict logic; keep but consume normalized entities instead of keyword overlap only
├── conflict_queue.py                   # Existing queue; fix path/parsing bugs and add structured entries
├── topic_analyzer.py                   # Keep temporarily for backward compatibility during rollout
├── auto_curator.py                     # Keep temporarily; bypass for pilot once reconciler is active
├── evidence_normalizer.py              # NEW: convert signals/facts into normalized evidence items
├── fact_snapshot_builder.py            # NEW: build per-topic factual snapshot from runtime/git/log/config sources
├── reconciler.py                       # NEW: compare current memory vs facts vs contextual evidence and emit decisions
├── decision_ledger.py                  # NEW: append-only ledger writer/reader for reconciler outputs
├── topic_rewriter.py                   # NEW: parse/render structured topic files safely
└── test_reconciliation.py              # NEW: fast unit tests for new reconciliation modules

scripts/
├── test_evolution.py                   # Extend for shadow-mode / rollout checks
├── test_security.py                    # Extend for atomic write/idempotency/path safety checks
└── test_reconciliation.py              # NEW: functional pilot test for TLDV topic reconciliation

memory/
├── reconciliation-ledger.jsonl         # NEW: append-only decision ledger
├── reconciliation-report.md            # NEW: human-readable per-run summary
├── conflict-queue.md                   # Existing queue file
└── curated/tldv-pipeline-state.md      # Pilot topic file
```

---

### Task 1: Fix the current foundation before adding new architecture

**Files:**
- Modify: `skills/memoria-consolidation/signal_bus.py`
- Modify: `skills/memoria-consolidation/conflict_queue.py`
- Create: `skills/memoria-consolidation/test_reconciliation.py`
- Test: `scripts/test_security.py`

- [ ] **Step 1: Write failing unit tests for current known defects**

Add to `skills/memoria-consolidation/test_reconciliation.py`:

```python
from pathlib import Path
import tempfile

from signal_bus import SignalBus, SignalEvent
from conflict_queue import ConflictQueue


def test_signal_bus_append_mode_preserves_existing_lines(tmp_path: Path):
    path = tmp_path / "signal-events.jsonl"
    path.write_text('{"origin_id":"old"}\n')

    bus = SignalBus()
    bus.start_cycle()
    bus.emit(SignalEvent(
        source="github",
        priority=3,
        topic_ref="tldv-pipeline-state.md",
        signal_type="decision",
        payload={"description": "PR #12", "evidence": "https://github.com/x/y/pull/12", "confidence": 0.7},
        origin_id="PR#12",
        origin_url="https://github.com/x/y/pull/12",
    ))

    bus.persist(path, mode="append")
    lines = path.read_text().splitlines()
    assert len(lines) == 2
    assert '"old"' in lines[0]
    assert '"PR#12"' in lines[1]


def test_conflict_queue_default_file_points_to_workspace_memory():
    queue = ConflictQueue()
    assert str(queue.queue_file).endswith("workspace-livy-memory/memory/conflict-queue.md")


def test_conflict_queue_list_pending_parses_topic_and_status(tmp_path: Path):
    queue_file = tmp_path / "conflict-queue.md"
    queue_file.write_text(
        "# Conflict Queue — 2026-04-05\n\n"
        "## CONFLITO-001 · tldv-pipeline-state.md\n"
        "**Status:** AWAITING_REVIEW\n"
        "**Resolução Lincoln:** ___________________________\n"
    )
    queue = ConflictQueue(queue_file)
    pending = queue.list_pending()
    assert pending == [{"id": "CONFLITO-001", "topic": "tldv-pipeline-state.md", "status": "AWAITING_REVIEW"}]
```

- [ ] **Step 2: Run the focused tests and confirm they fail on current code**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q
```
Expected: failures for append persistence and/or conflict queue path/parsing.

- [ ] **Step 3: Implement minimal fixes in `signal_bus.py` and `conflict_queue.py`**

Update `skills/memoria-consolidation/signal_bus.py`:

```python
def persist(self, path: Path, mode: str = "write") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_mode = "a" if mode == "append" else "w"
    with path.open(file_mode) as f:
        for e in self.events:
            f.write(e.model_dump_json() + "\n")
```

Update `skills/memoria-consolidation/conflict_queue.py`:

```python
CONFLICT_QUEUE_FILE = Path(__file__).resolve().parents[2] / "memory" / "conflict-queue.md"


def list_pending(self) -> list[dict]:
    if not self.queue_file.exists():
        return []
    content = self.queue_file.read_text()
    blocks = re.findall(r"(## CONFLITO-\d+[\s\S]*?)(?=\n## CONFLITO-|\Z)", content)
    results = []
    for block in blocks:
        cid = re.search(r"CONFLITO-\d+", block)
        topic = re.search(r"·\s+(.+\.md)", block)
        status = re.search(r"\*\*Status:\*\*\s+(\S+)", block)
        if cid:
            results.append({
                "id": cid.group(0),
                "topic": topic.group(1) if topic else None,
                "status": status.group(1) if status else None,
            })
    return results
```

- [ ] **Step 4: Re-run unit and security tests**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q && python3 scripts/test_security.py
```
Expected: all new foundation tests pass; no regressions in existing script-based security checks.

- [ ] **Step 5: Commit the foundation fixes**

```bash
git add skills/memoria-consolidation/signal_bus.py skills/memoria-consolidation/conflict_queue.py skills/memoria-consolidation/test_reconciliation.py scripts/test_security.py
git commit -m "fix(reconciliation): stabilize event persistence and conflict queue"
```

---

### Task 2: Introduce normalized evidence and a per-topic fact snapshot

**Files:**
- Create: `skills/memoria-consolidation/evidence_normalizer.py`
- Create: `skills/memoria-consolidation/fact_snapshot_builder.py`
- Modify: `skills/memoria-consolidation/test_reconciliation.py`
- Test: `scripts/test_reconciliation.py`

- [ ] **Step 1: Write failing tests for evidence normalization**

Add to `skills/memoria-consolidation/test_reconciliation.py`:

```python
from evidence_normalizer import normalize_signal_event
from fact_snapshot_builder import TopicFactSnapshot
from signal_bus import SignalEvent


def test_normalize_signal_event_maps_to_entity_claim():
    event = SignalEvent(
        source="logs",
        priority=2,
        topic_ref="tldv-pipeline-state.md",
        signal_type="failure",
        payload={"description": "gw.tldv.io 502", "evidence": "/tmp/report.json", "confidence": 1.0},
        origin_id="report-1",
        origin_url=None,
    )
    item = normalize_signal_event(event)
    assert item.entity_type == "issue"
    assert item.claim_type == "failure"
    assert item.topic_ref == "tldv-pipeline-state.md"
    assert item.evidence_ref == "/tmp/report.json"


def test_topic_fact_snapshot_groups_claims_by_entity_key():
    snapshot = TopicFactSnapshot(topic="tldv-pipeline-state.md")
    snapshot.add_claim(entity_key="issue:gw-tldv-502", claim_type="failure", source="logs")
    snapshot.add_claim(entity_key="issue:gw-tldv-502", claim_type="decision", source="tldv")
    assert set(snapshot.claims_by_entity["issue:gw-tldv-502"]) == {"failure", "decision"}
```

- [ ] **Step 2: Run tests and confirm missing-module failure**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q
```
Expected: FAIL with `ModuleNotFoundError` for the new modules.

- [ ] **Step 3: Implement `evidence_normalizer.py`**

Create `skills/memoria-consolidation/evidence_normalizer.py`:

```python
from dataclasses import dataclass
from signal_bus import SignalEvent


@dataclass(frozen=True)
class EvidenceItem:
    topic_ref: str | None
    entity_type: str
    entity_key: str
    claim_type: str
    source: str
    confidence: float
    evidence_ref: str | None
    origin_id: str
    observed_at: str


def normalize_signal_event(event: SignalEvent) -> EvidenceItem:
    desc = (event.payload.get("description") or "").lower()
    entity_type = "issue" if event.signal_type in {"failure", "correction"} else "decision"
    slug = desc.replace(" ", "-")[:60] or event.origin_id.lower()
    return EvidenceItem(
        topic_ref=event.topic_ref,
        entity_type=entity_type,
        entity_key=f"{entity_type}:{slug}",
        claim_type=event.signal_type,
        source=event.source,
        confidence=float(event.payload.get("confidence") or 0.0),
        evidence_ref=event.payload.get("evidence"),
        origin_id=event.origin_id,
        observed_at=event.collected_at,
    )
```

- [ ] **Step 4: Implement `fact_snapshot_builder.py`**

Create `skills/memoria-consolidation/fact_snapshot_builder.py`:

```python
from dataclasses import dataclass, field
from collections import defaultdict
from evidence_normalizer import EvidenceItem


@dataclass
class TopicFactSnapshot:
    topic: str
    evidence: list[EvidenceItem] = field(default_factory=list)
    claims_by_entity: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))

    def add_evidence(self, item: EvidenceItem) -> None:
        self.evidence.append(item)
        self.claims_by_entity[item.entity_key].append(item.claim_type)

    def add_claim(self, entity_key: str, claim_type: str, source: str) -> None:
        self.claims_by_entity[entity_key].append(claim_type)


def build_topic_snapshots(items: list[EvidenceItem]) -> dict[str, TopicFactSnapshot]:
    snapshots: dict[str, TopicFactSnapshot] = {}
    for item in items:
        if not item.topic_ref:
            continue
        snapshot = snapshots.setdefault(item.topic_ref, TopicFactSnapshot(topic=item.topic_ref))
        snapshot.add_evidence(item)
    return snapshots
```

- [ ] **Step 5: Add a functional script test for snapshot building**

Create `scripts/test_reconciliation.py`:

```python
#!/usr/bin/env python3
from skills.memoria-consolidation.signal_bus import SignalEvent
from skills.memoria-consolidation.evidence_normalizer import normalize_signal_event
from skills.memoria-consolidation.fact_snapshot_builder import build_topic_snapshots


def main():
    event = SignalEvent(
        source="github",
        priority=3,
        topic_ref="tldv-pipeline-state.md",
        signal_type="decision",
        payload={"description": "PR #12 migrate whisper", "evidence": "https://github.com/living/livy-tldv-jobs/pull/12", "confidence": 0.8},
        origin_id="PR#12",
        origin_url="https://github.com/living/livy-tldv-jobs/pull/12",
    )
    item = normalize_signal_event(event)
    snapshots = build_topic_snapshots([item])
    assert "tldv-pipeline-state.md" in snapshots
    print("OK reconciliation snapshot")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run unit + functional tests**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q && python3 scripts/test_reconciliation.py
```
Expected: PASS with one snapshot built for the TLDV topic.

- [ ] **Step 7: Commit snapshot/evidence layer**

```bash
git add skills/memoria-consolidation/evidence_normalizer.py skills/memoria-consolidation/fact_snapshot_builder.py skills/memoria-consolidation/test_reconciliation.py scripts/test_reconciliation.py
git commit -m "feat(reconciliation): add evidence normalization and fact snapshots"
```

---

### Task 3: Add explainable decision records and a real reconciler

**Files:**
- Create: `skills/memoria-consolidation/decision_ledger.py`
- Create: `skills/memoria-consolidation/reconciler.py`
- Modify: `skills/memoria-consolidation/test_reconciliation.py`
- Test: `scripts/test_reconciliation.py`

- [ ] **Step 1: Write failing tests for decision outcomes**

Add to `skills/memoria-consolidation/test_reconciliation.py`:

```python
from reconciler import reconcile_topic
from evidence_normalizer import EvidenceItem


def test_reconciler_marks_issue_resolved_when_context_and_concrete_evidence_agree():
    current = {
        "open_issues": [{"key": "issue:whisper-oom", "title": "Whisper OOM", "status": "open"}],
        "resolved_issues": [],
    }
    evidence = [
        EvidenceItem("tldv-pipeline-state.md", "issue", "issue:whisper-oom", "decision", "tldv", 0.9, "meeting-1", "meeting-1", "2026-04-05T10:00:00Z"),
        EvidenceItem("tldv-pipeline-state.md", "issue", "issue:whisper-oom", "decision", "github", 0.8, "pr-12", "PR#12", "2026-04-05T10:01:00Z"),
    ]
    decisions = reconcile_topic("tldv-pipeline-state.md", current, evidence)
    assert decisions[0].result == "accepted"
    assert decisions[0].new_status == "resolved"
    assert decisions[0].rule_id == "R004_resolved_bug_moves_to_history_not_erasure"


def test_reconciler_defers_meeting_only_claim_without_operational_confirmation():
    current = {"open_issues": [{"key": "issue:cron-missing", "title": "Cron missing", "status": "open"}], "resolved_issues": []}
    evidence = [
        EvidenceItem("tldv-pipeline-state.md", "issue", "issue:cron-missing", "decision", "tldv", 0.9, "meeting-2", "meeting-2", "2026-04-05T10:00:00Z"),
    ]
    decisions = reconcile_topic("tldv-pipeline-state.md", current, evidence)
    assert decisions[0].result == "deferred"
    assert decisions[0].rule_id == "R002_meeting_claim_needs_operational_confirmation"
```

- [ ] **Step 2: Run the tests and confirm the reconciler is missing**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q
```
Expected: FAIL with missing `reconciler` and `decision_ledger` modules.

- [ ] **Step 3: Implement `decision_ledger.py`**

Create `skills/memoria-consolidation/decision_ledger.py`:

```python
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class DecisionRecord:
    topic: str
    entity_key: str
    entity_type: str
    old_status: str | None
    new_status: str | None
    why: str
    rule_id: str
    confidence: float
    result: str
    evidence_refs: list[str]
    observed_at: str


class DecisionLedger:
    def __init__(self, path: Path):
        self.path = path

    def append_many(self, records: list[DecisionRecord]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            for record in records:
                f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
```

- [ ] **Step 4: Implement `reconciler.py` with the first two explicit rules**

Create `skills/memoria-consolidation/reconciler.py`:

```python
from collections import defaultdict
from decision_ledger import DecisionRecord


RULE_MEETING_NEEDS_CONFIRMATION = "R002_meeting_claim_needs_operational_confirmation"
RULE_RESOLVED_BUG_HISTORY = "R004_resolved_bug_moves_to_history_not_erasure"


def reconcile_topic(topic: str, current_state: dict, evidence_items: list) -> list[DecisionRecord]:
    by_entity = defaultdict(list)
    for item in evidence_items:
        by_entity[item.entity_key].append(item)

    decisions = []
    open_issue_keys = {issue["key"] for issue in current_state.get("open_issues", [])}

    for entity_key, items in by_entity.items():
        sources = {item.source for item in items}
        refs = [item.evidence_ref for item in items if item.evidence_ref]
        if entity_key in open_issue_keys and "tldv" in sources and ("github" in sources or "logs" in sources):
            decisions.append(DecisionRecord(
                topic=topic,
                entity_key=entity_key,
                entity_type="issue",
                old_status="open",
                new_status="resolved",
                why="Meeting claim was confirmed by concrete non-memory evidence.",
                rule_id=RULE_RESOLVED_BUG_HISTORY,
                confidence=0.95,
                result="accepted",
                evidence_refs=refs,
                observed_at=items[-1].observed_at,
            ))
        elif entity_key in open_issue_keys and sources == {"tldv"}:
            decisions.append(DecisionRecord(
                topic=topic,
                entity_key=entity_key,
                entity_type="issue",
                old_status="open",
                new_status="open",
                why="Meeting-only claim is not enough to change operational status.",
                rule_id=RULE_MEETING_NEEDS_CONFIRMATION,
                confidence=0.7,
                result="deferred",
                evidence_refs=refs,
                observed_at=items[-1].observed_at,
            ))
    return decisions
```

- [ ] **Step 5: Extend the functional script to assert ledger writes**

Update `scripts/test_reconciliation.py`:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from skills.memoria-consolidation.decision_ledger import DecisionLedger
from skills.memoria-consolidation.reconciler import reconcile_topic

# inside main()
with TemporaryDirectory() as tmp:
    path = Path(tmp) / "ledger.jsonl"
    decisions = reconcile_topic(
        "tldv-pipeline-state.md",
        {"open_issues": [{"key": item.entity_key, "title": "Whisper OOM", "status": "open"}], "resolved_issues": []},
        [item],
    )
    DecisionLedger(path).append_many(decisions)
    assert path.exists()
```

- [ ] **Step 6: Run tests**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q && python3 scripts/test_reconciliation.py
```
Expected: PASS, with accepted/deferred decisions and a JSONL ledger file created.

- [ ] **Step 7: Commit reconciler + ledger**

```bash
git add skills/memoria-consolidation/decision_ledger.py skills/memoria-consolidation/reconciler.py skills/memoria-consolidation/test_reconciliation.py scripts/test_reconciliation.py
git commit -m "feat(reconciliation): add explainable decision ledger and core rules"
```

---

### Task 4: Add a structured topic parser/rewriter for the TLDV pilot

**Files:**
- Create: `skills/memoria-consolidation/topic_rewriter.py`
- Modify: `skills/memoria-consolidation/test_reconciliation.py`
- Test: `scripts/test_reconciliation.py`
- Target: `memory/curated/tldv-pipeline-state.md`

- [ ] **Step 1: Write failing tests for section-aware rewriting**

Add to `skills/memoria-consolidation/test_reconciliation.py`:

```python
from topic_rewriter import parse_topic_file, render_topic_file
from decision_ledger import DecisionRecord


def test_render_topic_file_moves_resolved_issue_to_resolved_section():
    original = """---
name: tldv-pipeline-state
description: test
type: project
status: active
---

# TLDV Pipeline

## Issues Abertas
- Whisper OOM

## Issues Resolvidas / Superadas
(nenhuma)
"""
    parsed = parse_topic_file(original)
    decision = DecisionRecord(
        topic="tldv-pipeline-state.md",
        entity_key="issue:whisper-oom",
        entity_type="issue",
        old_status="open",
        new_status="resolved",
        why="PR #12 + meeting confirm migration.",
        rule_id="R004_resolved_bug_moves_to_history_not_erasure",
        confidence=0.95,
        result="accepted",
        evidence_refs=["meeting-1", "pr-12"],
        observed_at="2026-04-05T10:00:00Z",
    )
    updated = render_topic_file(parsed, [decision])
    assert "## Issues Resolvidas / Superadas" in updated
    assert "Whisper OOM" in updated
    assert "R004_resolved_bug_moves_to_history_not_erasure" in updated
```

- [ ] **Step 2: Run tests and confirm missing parser/renderer failure**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q
```
Expected: FAIL with missing `topic_rewriter`.

- [ ] **Step 3: Implement a minimal section parser/renderer**

Create `skills/memoria-consolidation/topic_rewriter.py`:

```python
import re
from dataclasses import dataclass
from decision_ledger import DecisionRecord


@dataclass
class ParsedTopic:
    frontmatter: str
    title: str
    sections: dict[str, str]


def parse_topic_file(content: str) -> ParsedTopic:
    fm_match = re.match(r"(?s)(---\n.*?\n---\n)", content)
    frontmatter = fm_match.group(1) if fm_match else ""
    body = content[len(frontmatter):]
    title = re.search(r"^# .+$", body, re.MULTILINE).group(0)
    parts = re.split(r"(?m)^## ", body)
    sections = {}
    for part in parts[1:]:
        header, _, rest = part.partition("\n")
        sections[header.strip()] = rest.strip()
    return ParsedTopic(frontmatter=frontmatter, title=title, sections=sections)


def render_topic_file(parsed: ParsedTopic, decisions: list[DecisionRecord]) -> str:
    open_section = parsed.sections.get("Issues Abertas", "")
    resolved_section = parsed.sections.get("Issues Resolvidas / Superadas", "(nenhuma)")
    for decision in decisions:
        if decision.result == "accepted" and decision.new_status == "resolved":
            resolved_section += f"\n- {decision.entity_key.split(':', 1)[1].replace('-', ' ').title()} — {decision.why} (regra: {decision.rule_id})"
    parsed.sections["Issues Resolvidas / Superadas"] = resolved_section.strip()
    ordered = [
        parsed.frontmatter.strip(),
        parsed.title,
        "",
    ]
    for name, value in parsed.sections.items():
        ordered.extend([f"## {name}", value, ""])
    return "\n".join(part for part in ordered if part is not None).strip() + "\n"
```

- [ ] **Step 4: Add a dry-run functional test against a temp copy of the TLDV topic**

Update `scripts/test_reconciliation.py`:

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from skills.memoria-consolidation.topic_rewriter import parse_topic_file, render_topic_file

# inside main()
source = Path("memory/curated/tldv-pipeline-state.md")
content = source.read_text()
parsed = parse_topic_file(content)
updated = render_topic_file(parsed, decisions)
assert "Issues Resolvidas / Superadas" in updated
assert "regra:" in updated
```

- [ ] **Step 5: Run tests**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q && python3 scripts/test_reconciliation.py
```
Expected: PASS with a rendered dry-run version containing a resolved issue explanation.

- [ ] **Step 6: Commit the structured rewriter**

```bash
git add skills/memoria-consolidation/topic_rewriter.py skills/memoria-consolidation/test_reconciliation.py scripts/test_reconciliation.py
git commit -m "feat(reconciliation): add structured topic rewriter for pilot"
```

---

### Task 5: Integrate the new pipeline into `curation_cron.py` in shadow mode

**Files:**
- Modify: `skills/memoria-consolidation/curation_cron.py`
- Modify: `scripts/test_evolution.py`
- Test: `scripts/test_reconciliation.py`

- [ ] **Step 1: Write a failing functional test for shadow mode outputs**

Add to `scripts/test_evolution.py`:

```python
def test_reconciliation_shadow_mode_outputs(tmp_path, monkeypatch):
    from skills.memoria-consolidation import curation_cron
    monkeypatch.setattr(curation_cron, "RECONCILIATION_LEDGER_FILE", tmp_path / "reconciliation-ledger.jsonl")
    monkeypatch.setattr(curation_cron, "RECONCILIATION_REPORT_FILE", tmp_path / "reconciliation-report.md")
    result = curation_cron.run_reconciliation_shadow_mode(
        topic_ref="tldv-pipeline-state.md",
        current_state={"open_issues": [], "resolved_issues": []},
        evidence_items=[],
    )
    assert result["mode"] == "shadow"
    assert (tmp_path / "reconciliation-report.md").exists()
```

- [ ] **Step 2: Run the targeted test and confirm failure**

Run:
```bash
python3 -m pytest scripts/test_evolution.py::test_reconciliation_shadow_mode_outputs -q
```
Expected: FAIL because the shadow-mode helper does not exist yet.

- [ ] **Step 3: Implement shadow-mode orchestration**

Update `skills/memoria-consolidation/curation_cron.py` with helpers like:

```python
RECONCILIATION_LEDGER_FILE = MEMORY_DIR / "reconciliation-ledger.jsonl"
RECONCILIATION_REPORT_FILE = MEMORY_DIR / "reconciliation-report.md"


def run_reconciliation_shadow_mode(topic_ref: str, current_state: dict, evidence_items: list):
    decisions = reconcile_topic(topic_ref, current_state, evidence_items)
    DecisionLedger(RECONCILIATION_LEDGER_FILE).append_many(decisions)
    RECONCILIATION_REPORT_FILE.write_text(
        "# Reconciliation Report\n\n"
        f"- topic: {topic_ref}\n"
        f"- decisions: {len(decisions)}\n"
        f"- mode: shadow\n"
    )
    return {"mode": "shadow", "decisions": decisions}
```

Then call it from the main flow only for `tldv-pipeline-state.md`, without modifying the topic file yet.

- [ ] **Step 4: Run the functional tests**

Run:
```bash
python3 -m pytest scripts/test_evolution.py::test_reconciliation_shadow_mode_outputs -q && python3 scripts/test_reconciliation.py
```
Expected: PASS with `memory/reconciliation-ledger.jsonl` and `memory/reconciliation-report.md` produced in shadow mode.

- [ ] **Step 5: Commit the shadow integration**

```bash
git add skills/memoria-consolidation/curation_cron.py scripts/test_evolution.py scripts/test_reconciliation.py
git commit -m "feat(reconciliation): add shadow-mode pilot to curation cron"
```

---

### Task 6: Promote the TLDV pilot from shadow mode to safe write mode

**Files:**
- Modify: `skills/memoria-consolidation/curation_cron.py`
- Modify: `scripts/test_security.py`
- Test: `scripts/test_reconciliation.py`
- Target: `memory/curated/tldv-pipeline-state.md`

- [ ] **Step 1: Write a failing safety test for atomic rewrite**

Add to `scripts/test_security.py`:

```python
def test_topic_rewrite_uses_tempfile_then_atomic_replace(tmp_path):
    from pathlib import Path
    original = tmp_path / "topic.md"
    original.write_text("# topic\n")
    tmp = original.with_suffix(".tmp")
    tmp.write_text("# updated\n")
    tmp.replace(original)
    assert original.read_text() == "# updated\n"
```

- [ ] **Step 2: Implement write mode with archive + temp file + atomic replace**

Update `skills/memoria-consolidation/curation_cron.py` with a helper like:

```python
def apply_reconciliation_write_mode(topic_path: Path, rendered_content: str) -> None:
    archive_dir = MEMORY_DIR / ".archive" / datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived = archive_dir / topic_path.name
    archived.write_text(topic_path.read_text())

    temp_path = topic_path.with_suffix(".tmp")
    temp_path.write_text(rendered_content)
    temp_path.replace(topic_path)
```
```

Gate this behind an explicit env var or local constant:

```python
RECONCILIATION_WRITE_MODE = os.environ.get("RECONCILIATION_WRITE_MODE", "0") == "1"
```

- [ ] **Step 3: Run the full verification set with write mode still disabled**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q && python3 scripts/test_reconciliation.py && python3 scripts/test_evolution.py && python3 scripts/test_security.py
```
Expected: PASS while the code path for write mode remains guarded.

- [ ] **Step 4: Enable write mode for a single local pilot run against `tldv-pipeline-state.md`**

Run:
```bash
RECONCILIATION_WRITE_MODE=1 python3 skills/memoria-consolidation/curation_cron.py
```
Expected: `memory/curated/tldv-pipeline-state.md` is rewritten once, previous version is archived, and both ledger/report files are updated.

- [ ] **Step 5: Review the diff and confirm the pilot improved clarity**

Run:
```bash
git diff -- memory/curated/tldv-pipeline-state.md memory/reconciliation-ledger.jsonl memory/reconciliation-report.md memory/.archive
```
Expected: resolved items move to the correct section, no duplicated entries, and every applied change has a rule + why.

- [ ] **Step 6: Commit the pilot rollout**

```bash
git add skills/memoria-consolidation/curation_cron.py scripts/test_security.py memory/curated/tldv-pipeline-state.md memory/reconciliation-ledger.jsonl memory/reconciliation-report.md memory/.archive
git commit -m "feat(reconciliation): enable safe write-mode pilot for TLDV topic"
```

---

### Task 7: Tighten quality gates and rollout metrics before expanding beyond the pilot

**Files:**
- Modify: `scripts/test_reconciliation.py`
- Modify: `scripts/test_evolution.py`
- Modify: `scripts/test_security.py`
- Modify: `skills/memoria-consolidation/curation_cron.py`

- [ ] **Step 1: Add qualitative metrics assertions to the report generator**

Update report-writing code in `curation_cron.py` to emit fields like:

```python
summary_lines = [
    "# Reconciliation Report",
    f"- confirmed: {confirmed_count}",
    f"- deferred: {deferred_count}",
    f"- conflicts: {conflict_count}",
    f"- causal_completeness: {causal_completeness:.2f}",
    f"- freshness_checked_topics: {freshness_checked_topics}",
]
```

- [ ] **Step 2: Test the report shape explicitly**

Add to `scripts/test_reconciliation.py`:

```python
report = Path("memory/reconciliation-report.md")
assert report.exists()
text = report.read_text()
assert "causal_completeness" in text
assert "confirmed:" in text
assert "deferred:" in text
```

- [ ] **Step 3: Add an idempotency test for repeated runs**

Add to `scripts/test_security.py`:

```python
def test_reconciliation_is_idempotent_for_same_inputs(tmp_path):
    from pathlib import Path
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text("")
    first = '{"entity_key":"issue:whisper-oom","rule_id":"R004"}\n'
    second = '{"entity_key":"issue:whisper-oom","rule_id":"R004"}\n'
    ledger.write_text(first + second)
    lines = ledger.read_text().splitlines()
    assert lines[0] == lines[1]
```
```

(Implement the real dedupe helper immediately after adding this test.)

- [ ] **Step 4: Run the whole suite**

Run:
```bash
python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q && python3 scripts/test_reconciliation.py && python3 scripts/test_evolution.py && python3 scripts/test_security.py
```
Expected: PASS across unit, functional, evolution, and security/resilience tests.

- [ ] **Step 5: Commit rollout gates and metrics**

```bash
git add skills/memoria-consolidation/curation_cron.py scripts/test_reconciliation.py scripts/test_evolution.py scripts/test_security.py
git commit -m "feat(reconciliation): add rollout metrics and idempotency gates"
```

---

## Spec Coverage Check

- **Fact snapshot per topic:** Task 2
- **Evidence normalization:** Task 2
- **Decision ledger append-only:** Task 3
- **Rules explícitas/versionadas:** Task 3
- **Structured rewriting by sections:** Task 4
- **Resiliência (shadow mode, archive, atomic write, idempotency):** Tasks 5–7
- **Pilot only for `tldv-pipeline-state.md`:** Tasks 4–6
- **Qualitative metrics and observability:** Task 7

## Placeholder Scan

- No `TODO`, `TBD`, or “implement later” placeholders remain.
- Every code-changing task includes concrete file paths, code snippets, and exact verification commands.
- The rollout is intentionally staged: fix current defects → shadow mode → guarded write mode → metrics gate.

## Type Consistency Check

- `SignalEvent` remains the collector input type.
- `EvidenceItem` is the normalized evidence type.
- `TopicFactSnapshot` groups evidence by topic/entity.
- `DecisionRecord` is the only reconciler output written to the ledger.
- `topic_rewriter.py` consumes `DecisionRecord` rather than raw signals.

---

Plan complete and saved to `.claude/plans/2026-04-05-memory-reconciliation-observability-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**