#!/usr/bin/env python3
"""
QW-3 DM Poller Cron — polls Telegram for /qw2approve and /qw2reject commands.
Runs every 15 minutes. Stores last processed update_id for idempotency.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]
STATE_FILE = _WS / ".research" / "qw2" / "dm_poller_state.json"
BOT_TOKEN_ENV = "TELEGRAM_MEMORY_BOT_TOKEN"
LINCOLN_ID = "7426291192"


def load_env():
    env_file = Path.home() / ".openclaw" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def get_last_update_id() -> int:
    if STATE_FILE.exists():
        try:
            return int(STATE_FILE.read_text().strip())
        except Exception:
            return 0
    return 0


def save_last_update_id(uid: int):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(str(uid))


def fetch_updates(offset: int, timeout: int = 5) -> list[dict]:
    token = os.environ.get(BOT_TOKEN_ENV) or os.environ.get("TELEGRAM_TOKEN")
    if not token:
        print("[dm-poller] No bot token")
        return []

    url = f"https://api.telegram.org/bot{token}/getUpdates?offset={offset}&timeout={timeout}&allowed_updates=message"
    try:
        with urllib.request.urlopen(url, timeout=timeout + 5) as resp:
            data = json.loads(resp.read())
            if data.get("ok"):
                return data.get("result", [])
    except Exception as e:
        print(f"[dm-poller] Fetch error: {e}")
    return []


def is_qw2_command(text: str) -> str | None:
    text = text.strip().lower()
    if text in ("/qw2approve", "/qw2confirm", "/qw2yes", "approve", "aprovar", "sim", "yes"):
        return "approve"
    if text in ("/qw2reject", "/qw2cancel", "/qw2no", "reject", "rejeitar", "nao", "no"):
        return "reject"
    return None


def main():
    load_env()
    sys.path.insert(0, str(_WS))

    from vault.qw3_callback_cron import handle_approve, handle_reject

    last_id = get_last_update_id()
    updates = fetch_updates(last_id + 1)

    if not updates:
        print("[dm-poller] No new updates")
        return

    processed = 0
    new_last_id = last_id

    for update in updates:
        update_id = update.get("update_id", 0)
        if update_id <= last_id:
            continue

        message = update.get("message", {})
        chat = message.get("chat", {})
        text = message.get("text", "")

        if str(chat.get("id")) != LINCOLN_ID:
            continue

        action = is_qw2_command(text)
        if not action:
            continue

        print(f"[dm-poller] {action}: {text[:50]}")

        if action == "approve":
            result = handle_approve()
            print(f"[dm-poller] Approved: {result.get('written', 0)} decisions")
        else:
            result = handle_reject()
            print(f"[dm-poller] Rejected: {result}")

        processed += 1
        new_last_id = max(new_last_id, update_id)

    if new_last_id > last_id:
        save_last_update_id(new_last_id)
        print(f"[dm-poller] Processed {processed} commands, saved offset {new_last_id}")


if __name__ == "__main__":
    main()
