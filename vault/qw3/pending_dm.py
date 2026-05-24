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
