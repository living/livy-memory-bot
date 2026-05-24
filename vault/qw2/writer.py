"""QW-2 writer: append decision to topic file with dedupe + write log."""
from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

QW2_BASE = Path(".research/qw2")
DECISIONS_DIR = Path("memory/vault/decisions")

def _written_refs_path() -> Path:
    return QW2_BASE / "written_refs.json"

def _write_log_path() -> Path:
    return QW2_BASE / "write_log.jsonl"

def load_written_refs() -> set[str]:
    path = _written_refs_path()
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        if isinstance(data, list):
            return set(data)
        return set(data.get("refs", []))
    except Exception:
        return set()

def add_to_written_refs(source_ref: str) -> None:
    refs = load_written_refs()
    refs.add(source_ref)
    path = _written_refs_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"refs": list(refs)}))

def append_to_write_log(source_ref: str, topic: str, action: str) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "source_ref": source_ref,
        "topic": topic,
        "action": action,
    }
    path = _write_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(entry) + "\n")

class QWWriter:
    """Append a decision to a topic file, with dedupe and write log."""

    def write(self, topic_path: Path, decision: dict) -> bool:
        source_ref = decision["source_ref"]
        refs = load_written_refs()
        if source_ref in refs:
            return False

        topic_path.parent.mkdir(parents=True, exist_ok=True)

        tags_str = ', '.join(decision.get('tags', []))
        # Trello uses last_activity; others use date
        date_val = decision.get('date') or decision.get('last_activity', '')[:10]
        entry = f"""
### {date_val} — {decision.get('source', 'unknown')}

> {decision.get('text', decision.get('card_name', 'No description'))}

- **Source:** {decision.get('source_ref')}
- **Confidence:** {decision.get('confidence', 'N/A')}
- **Tags:** {tags_str}
"""
        with open(topic_path, "a") as f:
            f.write(entry)

        add_to_written_refs(source_ref)
        append_to_write_log(source_ref, str(topic_path), "append")
        return True
