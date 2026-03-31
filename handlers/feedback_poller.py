#!/usr/bin/env python3
"""
Feedback Webhook Server — receives Telegram callback queries from 👍/👎 buttons.

Usage: python3 handlers/feedback_poller.py

Starts an HTTP server that receives Telegram webhook callbacks.
Telegram sends POST to https://srv1405423.hstgr.cloud/telegram-feedback/
This server parses the callback, writes to feedback-log.jsonl, and answers the callback.

To register webhook:
  curl -X POST "https://api.telegram.org/bot{BOT_TOKEN}/setWebhook" \
    -d "url=https://srv1405423.hstgr.cloud/telegram-feedback/"
"""

import json, os, sys
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

BOT_TOKEN = "8725269523:AAFqAFEFcbAa6daClbUiVH9qBLfzu46SMOQ"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
USER_ID = 7426291192  # Lincoln

FEEDBACK_LOG = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/feedback-log.jsonl")
PORT = int(os.environ.get("FEEDBACK_WEBHOOK_PORT", "8080"))

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
        if self.path != "/telegram-feedback/":
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

        data = callback.get("data", "")
        parts = data.split(":")
        if len(parts) >= 3:
            action, target, rating = parts[0], parts[1], parts[2]
            if rating in ("up", "down"):
                log_feedback(action, target, rating)
                print(f"Feedback logged: {action} {target} {rating}", flush=True)
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
        # Suppress default HTTP logging
        pass

def main():
    server = HTTPServer(("0.0.0.0", PORT), WebhookHandler)
    print(f"Feedback webhook server listening on port {PORT}", flush=True)
    server.serve_forever()

if __name__ == "__main__":
    main()
