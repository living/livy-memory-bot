#!/usr/bin/env python3
"""
QW-2 Callback Handler — process Telegram inline button callbacks.
Run via cron or triggered by callback query from Telegram.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))

from vault.qw2.writer import QWWriter
from vault.qw2.lock import acquire_lock, release_lock
from vault.qw2.consolidate import consolidate_topic, parse_topic_file
from vault.qw2.update_memory_index import update_memory_index

PENDING_DIR = _WS / "memory/vault/pending"
DECISIONS_DIR = _WS / "memory/vault/decisions"
LINCOLN_ID = "7426291192"


def get_pending_summary() -> list[dict]:
    """Get list of pending decisions with summary info."""
    decisions = []
    for pf in sorted(PENDING_DIR.glob("*.json")):
        if pf.stem == "archive":
            continue
        try:
            d = json.loads(pf.read_text())
            decisions.append({
                "source": d.get("source", "?").upper(),
                "text": d.get("text", d.get("card_name", "?"))[:60],
                "topic": d.get("topic", "general.md"),
                "confidence": d.get("confidence", "N/A"),
                "file": pf.name,
            })
        except Exception:
            pass
    return decisions


def confirm_pending() -> dict:
    """Write all pending decisions to topic files."""
    if not acquire_lock():
        return {"error": "already_running"}

    try:
        writer = QWWriter()
        pending_files = [pf for pf in PENDING_DIR.glob("*.json") if pf.stem != "archive"]
        written = 0
        topics_written = set()

        for pf in pending_files:
            try:
                d = json.loads(pf.read_text())
                topic = d.get("topic", "general.md")
                path = DECISIONS_DIR / topic
                if writer.write(path, d):
                    written += 1
                    topics_written.add(topic)
                # Archive
                archive_dir = PENDING_DIR / "archive"
                archive_dir.mkdir(exist_ok=True)
                pf.rename(archive_dir / pf.name)
            except Exception as e:
                print(f"Error processing {pf}: {e}")

        # Consolidate all modified topic files
        for topic in topics_written:
            try:
                consolidate_topic(DECISIONS_DIR / topic, dry_run=False)
            except Exception:
                pass

        # Update MEMORY.md
        try:
            update_memory_index()
        except Exception:
            pass

        return {"written": written, "topics": list(topics_written), "action": "confirmed"}
    finally:
        release_lock()


def cancel_pending() -> dict:
    """Archive all pending decisions without writing."""
    archive_dir = PENDING_DIR / "archive"
    archive_dir.mkdir(exist_ok=True)
    count = 0
    for pf in PENDING_DIR.glob("*.json"):
        if pf.stem == "archive":
            continue
        pf.rename(archive_dir / pf.name)
        count += 1
    return {"action": "cancelled", "count": count}


def build_summary_message() -> str:
    """Build summary of pending decisions for Telegram."""
    decisions = get_pending_summary()
    if not decisions:
        return "ℹ️ Sem decisões pendentes de revisão."

    lines = [f"📋 **{len(decisions)} decisões pendentes:**\n"]
    for d in decisions:
        conf = d["confidence"]
        conf_str = f"{conf:.0%}" if isinstance(conf, float) else str(conf)
        lines.append(f"• [{d['source']}] {d['text']}")
        lines.append(f"  → `{d['topic']}` (conf: {conf_str})")
        lines.append("")

    lines.append("---")
    lines.append("**[✅ Aprovar todas]** | **[❌ Rejeitar todas]**")
    return "\n".join(lines)


def send_telegram_summary() -> bool:
    """Send pending summary to Telegram with approve/reject buttons."""
    from openclaw import message as oc_message
    text = build_summary_message()
    buttons = [
        [
            {"text": "✅ Aprovar todas", "callback_data": "qw2_approve", "style": "success"},
            {"text": "❌ Rejeitar todas", "callback_data": "qw2_reject", "style": "danger"},
        ]
    ]
    try:
        oc_message(
            channel='telegram',
            action='send',
            target=LINCOLN_ID,
            message=text,
            buttons=buttons,
            accountId='memory'
        )
        return True
    except Exception as e:
        print(f"Telegram error: {e}")
        return False


def normalize_command(text: str) -> str | None:
    """Normalize a command string to action name."""
    text = text.strip().lower()
    # Handle /slash commands
    if text.startswith("/"):
        text = text.lstrip("/")
    # Map variations to canonical actions
    if text in ("qw2approve", "qw2_confirm", "approve", "aprovar", "sim", "yes"):
        return "qw2_approve"
    if text in ("qw2reject", "qw2_cancel", "reject", "rejeitar", "nao", "no"):
        return "qw2_reject"
    if text in ("qw2list", "qw2_list", "list"):
        return "qw2_list"
    return None


def process_callback(callback_data: str) -> dict:
    """Main entry point for processing a callback or command."""
    action = normalize_command(callback_data)
    if not action:
        return {"error": f"unknown_callback: {callback_data}"}

    if action == "qw2_approve":
        result = confirm_pending()
        return result
    elif action == "qw2_reject":
        result = cancel_pending()
        return result
    elif action == "qw2_list":
        send_telegram_summary()
        return {"action": "listed"}
    else:
        return {"error": f"unknown_callback: {action}"}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="QW-2 Callback Handler")
    parser.add_argument("--action", default="list", choices=["confirm", "cancel", "list"])
    parser.add_argument("--callback", help="callback_data from Telegram")
    args = parser.parse_args()

    if args.callback:
        result = process_callback(args.callback)
        print(json.dumps(result, indent=2))
    elif args.action == "confirm":
        result = confirm_pending()
        print(json.dumps(result, indent=2))
    elif args.action == "cancel":
        result = cancel_pending()
        print(json.dumps(result, indent=2))
    elif args.action == "list":
        decisions = get_pending_summary()
        print(json.dumps({"pending": decisions}, indent=2, default=str))
