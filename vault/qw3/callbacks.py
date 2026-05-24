"""QW-3 callback handlers for approve/reject — idempotent."""
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone

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
