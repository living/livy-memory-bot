"""
vault/ingest.py — Ingest memory/signal-events.jsonl into vault decisions/entities.
Phase 1B minimal functional implementation.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VAULT_ROOT = ROOT / "memory" / "vault"
DEFAULT_EVENTS = ROOT / "memory" / "signal-events.jsonl"


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"\s+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-") or "decision"


def map_signal_confidence(value: float | int | None) -> str:
    """
    Map numeric signal confidence to vault labels.
    Minimal policy for phase 1B:
    - >=0.9 => high
    - >=0.7 => medium
    - else => low
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return "low"
    if v >= 0.9:
        return "high"
    if v >= 0.7:
        return "medium"
    return "low"


def load_events(path: Path | str = DEFAULT_EVENTS) -> list[dict]:
    path = Path(path)
    if not path.exists():
        return []
    events: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return events


def deduplicate_events(events: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for event in events:
        key = str(event.get("origin_id") or event.get("event_id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(event)
    return out


def extract_signal(event: dict) -> dict | None:
    signal_type = event.get("signal_type")
    payload = event.get("payload", {})

    if signal_type not in {"decision", "topic_mentioned"}:
        return None

    return {
        "signal_type": signal_type,
        "description": payload.get("description", "").strip(),
        "evidence": payload.get("evidence") or event.get("origin_url") or "",
        "confidence": payload.get("confidence", 0.0),
        "origin_id": event.get("origin_id", ""),
        "origin_url": event.get("origin_url", ""),
        "topic_ref": event.get("topic_ref"),
        "collected_at": event.get("collected_at"),
    }


def _decision_frontmatter(decision: dict, conf: str, date_str: str) -> str:
    desc = decision.get("description", "").replace("\n", " ").strip()
    return f"""---
entity: {desc[:120] or 'Decision'}
type: decision
confidence: {conf}
sources:
  - type: signal_event
    ref: {decision.get('origin_url','')}
    retrieved: {date_str}
last_verified: {date_str}
verification_log: []
last_touched_by: livy-agent
draft: false
---
"""


def _stable_suffix(value: str, default: str = "evt") -> str:
    slug = _slugify(value)[:16]
    return slug or default


def upsert_decision(decision: dict) -> Path:
    decisions_dir = VAULT_ROOT / "decisions"
    decisions_dir.mkdir(parents=True, exist_ok=True)

    collected_at = decision.get("collected_at") or datetime.now(timezone.utc).isoformat()
    date_str = collected_at[:10]
    base_slug = _slugify(decision.get("description", "decision"))[:44]
    unique_suffix = _stable_suffix(decision.get("origin_id", ""), default="decision")
    filename = f"{date_str}-{base_slug}-{unique_suffix}.md"
    path = decisions_dir / filename

    # True upsert behavior for phase 1B: keep existing decision file stable
    if path.exists():
        return path

    conf = map_signal_confidence(decision.get("confidence"))
    frontmatter = _decision_frontmatter(decision, conf, date_str)

    links = []
    topic_ref = decision.get("topic_ref")
    if topic_ref:
        stem = Path(topic_ref).stem
        links.append(f"- Related entity: [[../entities/{stem}|{stem}]]")

    body_lines = [
        frontmatter,
        f"# {decision.get('description', 'Decision')}",
        "",
        "## Summary",
        decision.get("description", ""),
        "",
        "## Evidence",
        f"- {decision.get('evidence', '')}",
        "",
        "## Links",
    ]
    body_lines.extend(links if links else ["- none"])
    body = "\n".join(body_lines) + "\n"

    path.write_text(body, encoding="utf-8")
    return path


def _concept_frontmatter(topic: dict, conf: str, date_str: str) -> str:
    desc = topic.get("description", "").replace("\n", " ").strip()
    return f"""---
entity: {desc[:120] or 'Concept'}
type: concept
confidence: {conf}
sources:
  - type: signal_event
    ref: {topic.get('origin_url','')}
    retrieved: {date_str}
last_verified: {date_str}
verification_log: []
last_touched_by: livy-agent
draft: false
---
"""


def upsert_concept(topic: dict) -> Path:
    concepts_dir = VAULT_ROOT / "concepts"
    concepts_dir.mkdir(parents=True, exist_ok=True)

    collected_at = topic.get("collected_at") or datetime.now(timezone.utc).isoformat()
    date_str = collected_at[:10]
    slug = _slugify(topic.get("description", "concept"))[:48]
    unique_suffix = _stable_suffix(topic.get("origin_id", ""), default="topic")
    path = concepts_dir / f"{slug}-{unique_suffix}.md"

    if path.exists():
        return path

    conf = map_signal_confidence(topic.get("confidence"))
    frontmatter = _concept_frontmatter(topic, conf, date_str)
    body = "\n".join([
        frontmatter,
        f"# {topic.get('description', 'Concept')}",
        "",
        "## Summary",
        topic.get("description", ""),
        "",
        "## Evidence",
        f"- {topic.get('evidence', '')}",
        "",
        "## Links",
        "- none",
        "",
    ])
    path.write_text(body, encoding="utf-8")
    return path


def _count_md(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for p in path.glob("*.md"))


def _update_index() -> None:
    index = VAULT_ROOT / "index.md"
    entities = _count_md(VAULT_ROOT / "entities")
    decisions = _count_md(VAULT_ROOT / "decisions")
    evidence = _count_md(VAULT_ROOT / "evidence")

    lines = [
        "# Vault Index",
        "",
        f"## Entities ({entities})",
        "",
        f"## Decisions ({decisions})",
        "",
        f"## Evidence ({evidence})",
        "",
    ]
    index.write_text("\n".join(lines), encoding="utf-8")


def _append_log(summary: dict) -> None:
    log = VAULT_ROOT / "log.md"
    now = datetime.now(timezone.utc).date().isoformat()
    lines = [
        f"## [{now}] ingest | process signal-events.jsonl",
        f"  total: {summary['total']}",
        f"  decisions: {summary['decisions']}",
        f"  topics: {summary['topics']}",
        "",
    ]
    mode = "a" if log.exists() else "w"
    with log.open(mode, encoding="utf-8") as f:
        f.write("\n".join(lines))


def run_ingest(events_path: Path | str = DEFAULT_EVENTS) -> dict:
    VAULT_ROOT.mkdir(parents=True, exist_ok=True)
    (VAULT_ROOT / "decisions").mkdir(parents=True, exist_ok=True)
    (VAULT_ROOT / "concepts").mkdir(parents=True, exist_ok=True)

    events = load_events(events_path)
    deduped = deduplicate_events(events)

    decisions_count = 0
    topics_count = 0

    for event in deduped:
        signal = extract_signal(event)
        if not signal:
            continue
        if signal["signal_type"] == "decision":
            upsert_decision(signal)
            decisions_count += 1
        elif signal["signal_type"] == "topic_mentioned":
            upsert_concept(signal)
            topics_count += 1

    summary = {
        "total": len(events),
        "deduped": len(deduped),
        "decisions": decisions_count,
        "topics": topics_count,
    }

    _update_index()
    _append_log(summary)
    return summary


if __name__ == "__main__":
    result = run_ingest(DEFAULT_EVENTS)
    print(json.dumps(result, ensure_ascii=False, indent=2))
