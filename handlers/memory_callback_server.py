#!/usr/bin/env python3
"""
Callback Webhook Server — receives Telegram callback queries from memory-agent thumbs.

Receives callbacks from the @livy_agentic_memory_bot (8738927361) that sends
the autoresearch files and summary. Logs feedback to feedback-log.jsonl so
the next cron run can read it.

Usage: python3 handlers/memory_callback_server.py

Starts an HTTP server that receives Telegram webhook callbacks.
Telegram sends POST to https://srv1405423.hstgr.cloud/memory-callback/
This server parses the callback, writes to feedback-log.jsonl, and answers the callback.
"""

import json, os, sys
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

BOT_TOKEN = "8738927361:AAFIG5E9-ND9hwb2onxbLLBi03aQZzofuoE"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
USER_ID = 7426291192  # Lincoln

FEEDBACK_LOG = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/feedback-log.jsonl")
PORT = int(os.environ.get("MEMORY_CALLBACK_PORT", "8081"))

def log_feedback(action, target, rating):
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "target": target,
        "rating": rating,
        "note": None,
        "source": "memory-agent-callback",
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

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/memory-callback/":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")

        try:
            update = json.loads(body)
        except json.JSONDecodeError:
            self.send_response(400)
            self.end_headers()
            return

        callback = update.get("callback_query", {})
        if not callback:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        # Filter: only Lincoln's DMs
        user = callback.get("from", {})
        if user.get("id") != USER_ID:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"ok":true}')
            return

        # Parse callback data: feedback:action:target:rating
        data = callback.get("data", "")
        parts = data.split(":")
        if len(parts) >= 3:
            action, target, rating = parts[0], parts[1], parts[2]
            if rating in ("up", "down"):
                log_feedback(action, target, rating)
                answer_callback(callback.get("id"), f"👍" if rating == "up" else "👎")
            else:
                answer_callback(callback.get("id"))
        else:
            answer_callback(callback.get("id"))

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"ok":true}')

    def log_message(self, format, *args):
        pass  # Suppress default logging

if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Memory callback server starting on port {PORT}", flush=True)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Bot token: {BOT_TOKEN[:20]}...", flush=True)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Feedback log: {FEEDBACK_LOG}", flush=True)
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Listening on http://0.0.0.0:{PORT}/memory-callback/", flush=True)
    server.serve_forever()
