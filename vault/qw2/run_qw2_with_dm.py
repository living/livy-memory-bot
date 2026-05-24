#!/usr/bin/env python3
"""
QW-2 dry-run + send Telegram DM with inline buttons for pending decisions.
Combines run.py dry-run with DM notification in one script.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))

from vault.qw2.run import run
from vault.qw2.lock import acquire_lock, release_lock

DM_FILE = _WS / ".research/qw2/.pending_confirmation/dry_run_dm.txt"
LINCOLN_ID = "7426291192"


def send_telegram(text: str, buttons: list) -> bool:
    """Send Telegram message via openclaw CLI."""
    import openclaw

    try:
        openclaw.message(
            channel='telegram',
            action='send',
            target=LINCOLN_ID,
            message=text,
            buttons=buttons,
            accountId='memory'
        )
        return True
    except Exception as e:
        print(f"[QW-2] Telegram send error: {e}")
        return False


def main():
    print("[QW-2] Starting dry-run...")

    # Acquire lock
    if not acquire_lock():
        print("[QW-2] Already running, skipping.")
        sys.exit(0)

    try:
        # Run dry-run
        result = run(source='all', dry_run=True, since_days=7)
        print(f"[QW-2] Dry-run complete: {result['processed']} processed, {result['routing_failed']} pending")

        # Build DM content
        if not result['dm_candidates']:
            print("[QW-2] No pending decisions, DM not sent")
            return

        lines = [
            f"🔍 QW-2 dry-run — {result['processed']} decisões processadas\n",
            f"📝 Escritas: {result['written']} | Duplicadas: {result['skipped_dedupe']} | Filtradas: {result['skipped_filter']}\n",
            f"⚠️ Routings falhados (→ revisão): {result['routing_failed']}\n",
            "---",
            "**Decisões pendentes de revisão:**",
        ]
        for d in result['dm_candidates']:
            conf = d.get("confidence", 0)
            text = d.get("text", "")[:80]
            source = d.get("source", "?").upper()
            topic = d.get("topic", "unknown")
            lines.append(f"• [{source}] {text}")
            lines.append(f"  → {topic} (conf: {conf:.0%})")

        lines.append("---")
        lines.append("**[✅ Confirmar — próximo run escreve]** | **[❌ Cancelar]**")

        text = "\n".join(lines)

        # Send to Telegram
        buttons = [
            [
                {"text": "✅ Confirmar", "callback_data": "qw2_confirm", "style": "success"},
                {"text": "❌ Cancelar", "callback_data": "qw2_cancel", "style": "danger"},
            ]
        ]

        success = send_telegram(text, buttons)
        if success:
            print(f"[QW-2] Telegram DM sent with buttons")
        else:
            print(f"[QW-2] Telegram DM failed, saving to file")
            DM_FILE.parent.mkdir(parents=True, exist_ok=True)
            DM_FILE.write_text(text)

    finally:
        release_lock()


if __name__ == "__main__":
    main()
