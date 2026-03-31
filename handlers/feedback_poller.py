#!/usr/bin/env python3
"""
Feedback Poller — polling Telegram for callback queries from 👍/👎 buttons.

Usage: python3 handlers/feedback_poller.py

Runs once per invocation (cron-friendly). Designed to be called every 1 minute.
"""

import json
import requests
from datetime import datetime
from pathlib import Path

BOT_TOKEN = "8738927361:AAFIG5E9-ND9hwb2onxbLLBi03aQZzofuoE"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
USER_ID = 7426291192  # Lincoln

STATE_FILE = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/.feedback_poller_state")
FEEDBACK_LOG = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/feedback-log.jsonl")


def get_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_update_id": 0}


def save_state(state):
    STATE_FILE.write_text(json.dumps(state))


def log_feedback(action, target, rating):
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "target": target,
        "rating": rating,
        "note": None,
    }
    with FEEDBACK_LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def poll():
    state = get_state()
    last_id = state["last_update_id"]
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 5, "offset": last_id + 1, "limit": 10}

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
    except Exception as e:
        print(f"Erro ao buscar updates: {e}", flush=True)
        return

    for update in updates:
        update_id = update.get("update_id", 0)
        callback = update.get("callback_query", {})
        if not callback:
            continue

        # Only process callbacks from Lincoln's DM
        user = callback.get("from", {})
        if user.get("id") != USER_ID:
            continue

        data = callback.get("data", "")
        parts = data.split(":")
        if len(parts) >= 3:
            action, target, rating = parts[0], parts[1], parts[2]
            if rating in ("up", "down"):
                log_feedback(action, target, rating)
                print(f"Feedback: {action} {target} {rating}", flush=True)

        # Answer callback to remove loading state
        callback_id = callback.get("id")
        if callback_id:
            requests.post(
                f"{BASE_URL}/answerCallbackQuery",
                json={"callback_query_id": callback_id},
            )

        if update_id > last_id:
            last_id = update_id

    save_state({"last_update_id": last_id})


def main():
    poll()


if __name__ == "__main__":
    main()
