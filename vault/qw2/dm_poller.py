#!/usr/bin/env python3
"""
QW-2 DM Poller — poll Telegram for /qw2approve and /qw2reject commands.
Lightweight polling: stores last processed update_id, fetches new updates.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_WS))

from vault.qw2.callback_handler import confirm_pending, cancel_pending, get_pending_summary

BOT_TOKEN_ENV = "TELEGRAM_MEMORY_BOT_TOKEN"  # token do memory bot
STATE_FILE = _WS / ".research" / "qw2" / "dm_poller_state.json"
POLL_INTERVAL = 30  # seconds between polls


def get_last_update_id() -> int:
    if STATE_FILE.exists():
        try:
            return int(STATE_FILE.read_text().strip())
        except Exception:
            return 0
    return 0


def save_last_update_id(update_id: int):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(str(update_id))


def fetch_updates(offset: int, timeout: int = 5) -> list[dict]:
    """Fetch Telegram updates using getUpdates API."""
    import urllib.request

    token = os.environ.get(BOT_TOKEN_ENV) or os.environ.get("TELEGRAM_TOKEN")
    if not token:
        # Try to get from OpenClaw config
        try:
            import subprocess
            result = subprocess.run(
                ["openclaw", "config", "get", "channels.telegram.accounts.memory.botToken"],
                capture_output=True, text=True, timeout=5
            )
            token = result.stdout.strip()
        except Exception:
            pass

    if not token:
        print("[poller] No bot token found")
        return []

    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout={timeout}&allowed_updates=message"
    try:
        with urllib.request.urlopen(url, timeout=timeout + 5) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                return data.get("result", [])
    except Exception as e:
        print(f"[poller] Error fetching updates: {e}")
    return []


def is_qw2_command(text: str) -> tuple[str | None, str | None]:
    """
    Check if message text is a QW-2 command.
    Returns (action, rest_of_message) or (None, None).
    """
    text = text.strip().lower()
    if text in ("/qw2approve", "/qw2confirm", "/qw2yes"):
        return ("approve", "")
    if text in ("/qw2reject", "/qw2cancel", "/qw2no"):
        return ("reject", "")
    # Also accept plain approve/reject
    if text in ("approve", "aprovar", "sim", "yes"):
        return ("approve", "")
    if text in ("reject", "rejeitar", "nao", "no"):
        return ("reject", "")
    return (None, None)


def process_updates() -> dict:
    """
    Poll for new Telegram messages and process QW-2 commands.
    Returns summary of what was processed.
    """
    last_id = get_last_update_id()
    updates = fetch_updates(last_id + 1)

    if not updates:
        return {"processed": 0, "actions": []}

    processed = 0
    actions = []
    new_last_id = last_id

    for update in updates:
        update_id = update.get("update_id", 0)
        if update_id <= last_id:
            continue

        message = update.get("message", {})
        chat = message.get("chat", {})
        text = message.get("text", "")

        # Only accept from Lincoln
        if str(chat.get("id")) != "7426291192":
            continue

        action, _ = is_qw2_command(text)
        if not action:
            continue

        # Process the command
        if action == "approve":
            result = confirm_pending()
        else:
            result = cancel_pending()

        actions.append({"action": action, "result": result})
        processed += 1
        new_last_id = max(new_last_id, update_id)

        print(f"[poller] Processed {action}: {result}")

    if new_last_id > last_id:
        save_last_update_id(new_last_id)

    return {"processed": processed, "actions": actions}


def send_notification_dm() -> bool:
    """Send a DM to Lincoln about pending decisions."""
    pending = get_pending_summary()
    if not pending:
        return False

    from openclaw import message as oc_message

    lines = [f"📋 *{len(pending)} decisões pendentes de revisão:*\n"]
    for d in pending:
        conf = d["confidence"]
        conf_str = f"{conf:.0%}" if isinstance(conf, float) else str(conf)
        lines.append(f"• [{d['source']}] {d['text']}")
        lines.append(f"  → `{d['topic']}` (conf: {conf_str})")

    lines.append("\n---")
    lines.append("Responde com `/qw2approve` para gravar ou `/qw2reject` para cancelar.")

    text = "\n".join(lines)
    try:
        oc_message(
            channel='telegram',
            action='send',
            target='7426291192',
            message=text,
            accountId='memory',
        )
        return True
    except Exception as e:
        print(f"[poller] Error sending DM: {e}")
        return False


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="QW-2 DM Poller")
    parser.add_argument("--poll", action="store_true", help="Poll once for commands")
    parser.add_argument("--notify", action="store_true", help="Send pending notification DM")
    args = parser.parse_args()

    if args.poll:
        result = process_updates()
        print(json.dumps(result, indent=2, default=str))
    elif args.notify:
        sent = send_notification_dm()
        print(f"Notification DM sent: {sent}")
    else:
        # Default: poll and process
        result = process_updates()
        if result["processed"] > 0:
            print(json.dumps(result, indent=2, default=str))
        else:
            print("[poller] No commands processed")
