#!/usr/bin/env python3
"""
Feedback Poller — polls Telegram for callback queries from 👍/👎 buttons.

Usage: python3 handlers/feedback_poller.py

Polling interval: 5 seconds
Stores feedback in memory/feedback-log.jsonl
"""

import json, os, time
from pathlib import Path
from datetime import datetime
import requests

BOT_TOKEN = "8725269523:AAFqAFEFcbAa6daClbUiVH9qBLfzu46SMOQ"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
USER_ID = 7426291192  # Lincoln

FEEDBACK_LOG = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/feedback-log.jsonl")
POLL_INTERVAL = 5  # seconds between polls

# Track processed callback IDs to avoid duplicates
processed_callbacks = set()

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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Feedback logged: {action}:{target}:{rating}", flush=True)

def answer_callback(callback_id, text=None):
    """Tell Telegram to dismiss the loading spinner."""
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    try:
        requests.post(f"{BASE_URL}/answerCallbackQuery", json=payload, timeout=5)
    except Exception as e:
        print(f"answerCallbackQuery error: {e}", flush=True)

def process_callback(callback):
    """Process a single callback query."""
    callback_id = callback.get("id")
    if callback_id in processed_callbacks:
        return
    processed_callbacks.add(callback_id)

    user = callback.get("from", {})
    if user.get("id") != USER_ID:
        return

    data = callback.get("data", "")
    parts = data.split("|")
    if len(parts) >= 4 and parts[0] == "feedback":
        action, action_id, target, rating = parts[0], parts[1], parts[2], parts[3]
        if rating in ("up", "down"):
            log_feedback(f"{action_id}:{target}", target, rating)
            answer_callback(callback_id, f"👍" if rating == "up" else "👎")
        else:
            answer_callback(callback_id)
    else:
        answer_callback(callback_id)

def poll_callbacks():
    """Poll for callback queries continuously."""
    offset = None
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Polling started (interval: {POLL_INTERVAL}s)", flush=True)
    while True:
        try:
            params = {"timeout": POLL_INTERVAL}
            if offset:
                params["offset"] = offset
            resp = requests.get(f"{BASE_URL}/getUpdates", params=params, timeout=POLL_INTERVAL + 5)
            data = resp.json()
            if data.get("ok"):
                for update in data.get("result", []):
                    offset = update.get("update_id", 0) + 1
                    callback = update.get("callback_query")
                    if callback:
                        process_callback(callback)
        except Exception as e:
            print(f"Polling error: {e}", flush=True)
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Feedback poller starting", flush=True)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Bot token: {BOT_TOKEN[:20]}...", flush=True)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Feedback log: {FEEDBACK_LOG}", flush=True)
    poll_callbacks()
