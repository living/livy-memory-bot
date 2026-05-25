# QW-2 Callback Handler Skill

Handles Telegram inline button callbacks for QW-2 pending decisions workflow.

## Trigger

When a Telegram message contains callback_data starting with `qw2_` (qw2_confirm, qw2_cancel, qw2_approve, qw2_reject).

## Workflow

### qw2_confirm / qw2_approve
1. Read pending decisions from `memory/vault/pending/`
2. Send Telegram message listing decisions with approve/reject buttons
3. Wait for user confirmation
4. On approve: write decisions to appropriate topic files → consolidate → update MEMORY.md
5. On reject: archive pending files without writing
6. Send confirmation message to Telegram

### qw2_cancel / qw2_reject
1. Archive all pending decisions
2. Send cancellation message to Telegram

## Implementation

```python
# vault/qw2/callback_handler.py
from pathlib import Path
from vault.qw2.writer import QWWriter
from vault.qw2.lock import acquire_lock, release_lock
import json

PENDING_DIR = Path("memory/vault/pending")
DECISIONS_DIR = Path("memory/vault/decisions")

def process_callback(action: str) -> dict:
    if action in ("qw2_confirm", "qw2_approve"):
        return confirm_pending()
    elif action in ("qw2_cancel", "qw2_reject"):
        return cancel_pending()

def confirm_pending() -> dict:
    if not acquire_lock():
        return {"error": "lock_failed"}
    try:
        writer = QWWriter()
        pending = list(PENDING_DIR.glob("*.json"))
        written = 0
        for pf in pending:
            d = json.loads(pf.read_text())
            topic = d.get("topic", "general.md")
            path = DECISIONS_DIR / topic
            if writer.write(path, d):
                written += 1
            # Archive
            archive_dir = PENDING_DIR / "archive"
            archive_dir.mkdir(exist_ok=True)
            pf.rename(archive_dir / pf.name)
        return {"written": written, "action": "confirmed"}
    finally:
        release_lock()

def cancel_pending() -> dict:
    archive_dir = PENDING_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)
    for pf in PENDING_DIR.glob("*.json"):
        pf.rename(archive_dir / pf.name)
    return {"action": "cancelled", "count": len(list(archive_dir.glob("*.json")))}
```

## Send Confirmation Telegram

Use message tool with inline buttons:
```
action: send
channel: telegram
target: 7426291192
accountId: memory
message: "🔍 X decisões pendentes:\n\n• ...\n\nConfirmar?"
buttons: [[{"text": "✅ Aprovar tudo", "callback_data": "qw2_approve", "style": "success"}, {"text": "❌ Rejeitar", "callback_data": "qw2_reject", "style": "danger"}]]
```
