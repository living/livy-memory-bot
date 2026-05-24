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
