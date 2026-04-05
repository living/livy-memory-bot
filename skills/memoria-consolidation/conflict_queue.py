#!/usr/bin/env python3
"""
conflict_queue.py — Manages the conflict queue file (memory/conflict-queue.md).
Provides add, list, resolve operations.
"""
import re
from datetime import datetime, timezone
from pathlib import Path

from conflict_detector import Conflict


CONFLICT_QUEUE_FILE = Path(__file__).resolve().parents[2] / "memory" / "conflict-queue.md"


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
        entries = re.findall(r"(## CONFLITO-\d+.*?)(?=\n## CONFLITO-|$)", content, re.DOTALL)
        results = []
        for entry in entries:
            cid = re.search(r"##\s+(CONFLITO-\d+)", entry)
            topic = re.search(r"##\s+CONFLITO-\d+\s+·\s+(.+)", entry)
            status = re.search(r"\*\*Status:\*\*\s+([^\n]+)", entry)
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
