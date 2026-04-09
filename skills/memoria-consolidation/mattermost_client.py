"""Mattermost webhook client for triage payload emission.

Task 6 requirements:
- POST to webhook URL with structured JSON payload
- timeout handling
- no framework dependency (urllib only)
"""

from __future__ import annotations

import html
import json
from typing import Any
from urllib import error, request


class MattermostClient:
    """Send triage payloads to Mattermost incoming webhook."""

    def __init__(self, webhook_url: str, timeout_seconds: float = 10.0) -> None:
        if not webhook_url:
            raise ValueError("webhook_url is required")
        self.webhook_url = webhook_url
        self.timeout_seconds = float(timeout_seconds)

    def _build_payload(self, triage_payload: dict[str, Any]) -> dict[str, Any]:
        signal_id = str(triage_payload.get("id", "unknown"))
        tier = str(triage_payload.get("tier", "?"))
        causal_score = triage_payload.get("causal_score", "?")
        signal_text = html.escape(str(triage_payload.get("signal_text", "")))
        fact_check_passed = bool(triage_payload.get("fact_check_passed", False))

        return {
            "id": signal_id,
            "text": f"🚨 Triage required for signal `{signal_id}` (Tier {tier})\n{signal_text}",
            "attachments": [
                {
                    "color": "#ff8800" if tier in {"A", "B"} else "#888888",
                    "fields": [
                        {"short": True, "title": "Signal ID", "value": signal_id},
                        {"short": True, "title": "Tier", "value": tier},
                        {"short": True, "title": "Causal score", "value": str(causal_score)},
                        {"short": True, "title": "Fact-check", "value": "passed" if fact_check_passed else "failed"},
                    ],
                }
            ],
        }

    def send_triage_payload(self, triage_payload: dict[str, Any]) -> bool:
        body = self._build_payload(triage_payload)
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")

        req = request.Request(self.webhook_url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")

        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as resp:  # nosec B310
                resp.read()
            return True
        except error.HTTPError as exc:
            # Explicit timeout-ish handling demanded by tests/requirements.
            if exc.code == 504:
                raise
            return False
        except error.URLError:
            return False
