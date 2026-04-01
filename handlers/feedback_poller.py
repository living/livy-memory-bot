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

BOT_TOKEN = os.getenv("FEEDBACK_BOT_TOKEN", "")
if not BOT_TOKEN:
    raise ValueError("FEEDBACK_BOT_TOKEN env var not set")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
# Allowed user IDs for memory-general feedback (comma-separated in env var)
# Empty means accept ALL users
ALLOWED_USER_IDS = set(
    int(uid.strip()) for uid in os.getenv("MEETINGS_TLDV_ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
) if os.getenv("MEETINGS_TLDV_ALLOWED_USER_IDS") else set()

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

def _log_feedback_to_skill(skill: str, action: str, target: str, rating: str, callback):
    """Route feedback to the correct skill-specific log file."""
    FEEDBACK_FILES = {
        "meetings_tldv": Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/meetings-tldv-feedback-log.jsonl"),
        "memory_general": Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/feedback-log.jsonl"),
    }
    user = callback.get("from", {})
    user_id = user.get("id")
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "user_id": user_id,
        "action": action,
        "target": target,
        "rating": rating,
        "note": None,
    }
    log_file = FEEDBACK_FILES.get(skill, FEEDBACK_FILES["memory_general"])
    with log_file.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{skill}] Feedback: {action}:{target}:{rating}", flush=True)

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

    data = callback.get("data", "")
    parts = data.split("|")
    if not parts:
        answer_callback(callback_id)
        return

    skill_prefix = parts[0]

    if skill_prefix == "meetings_tldv":
        # meetings_tldv|{mode}|{query_hash}|{rating}
        # Optional: restrict to allowed users if MEETINGS_TLDV_ALLOWED_USER_IDS is set
        user = callback.get("from", {})
        user_id = user.get("id")
        if ALLOWED_USER_IDS and user_id not in ALLOWED_USER_IDS:
            return
        if len(parts) >= 4 and parts[3] in ("up", "down"):
            mode = parts[1]
            query_hash = parts[2]
            rating = parts[3]
            action = f"{mode}|{query_hash}"
            target = mode
            _log_feedback_to_skill("meetings_tldv", action, target, rating, callback)
            answer_callback(callback_id, "👍" if rating == "up" else "👎")
        else:
            answer_callback(callback_id)

    elif skill_prefix == "feedback":
        # memory-general: feedback|{action_id}|{target}|{rating}
        user = callback.get("from", {})
        user_id = user.get("id")
        # Optional: restrict to allowed users for memory-general
        if ALLOWED_USER_IDS and user_id not in ALLOWED_USER_IDS:
            return
        if len(parts) >= 4 and parts[3] in ("up", "down"):
            action = "|".join(parts[1:3])
            target = parts[2]
            rating = parts[3]
            _log_feedback_to_skill("memory_general", action, target, rating, callback)
            answer_callback(callback_id, "👍" if rating == "up" else "👎")
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
