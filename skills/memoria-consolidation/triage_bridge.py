"""Bridge to route shadow triage decisions to Mattermost and audit logs."""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error as urllib_error


DEFAULT_AUDIT_LOG_PATH = Path(__file__).resolve().parents[2] / "memory" / "triage-decisions.jsonl"


def _load_mattermost_client_class():
    """Load MattermostClient from sibling file (hyphenated directory-safe)."""
    module_name = "memoria_consolidation_mattermost_client"
    cached = sys.modules.get(module_name)
    if cached is not None and hasattr(cached, "MattermostClient"):
        return cached.MattermostClient

    file_path = Path(__file__).resolve().parent / "mattermost_client.py"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load Mattermost client from {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module.MattermostClient


class TriageBridge:
    def __init__(
        self,
        webhook_url: str,
        audit_log_path: str | Path | None = None,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.webhook_url = webhook_url
        self.audit_log_path = Path(audit_log_path) if audit_log_path else DEFAULT_AUDIT_LOG_PATH
        self.timeout_seconds = timeout_seconds

    def _utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _append_audit_log(self, record: dict[str, Any]) -> None:
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.audit_log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _post_to_mattermost(self, triage_payload: dict[str, Any]) -> bool:
        Client = _load_mattermost_client_class()
        client = Client(webhook_url=self.webhook_url, timeout_seconds=self.timeout_seconds)
        return client.send_triage_payload(triage_payload)

    def route_for_triage(self, triage_payload: dict[str, Any]) -> dict[str, Any]:
        signal_id = str(triage_payload.get("id", "unknown"))
        tier = str(triage_payload.get("tier", "C"))

        if tier == "C":
            decision = {
                "timestamp": self._utc_now_iso(),
                "action": "route_to_triage",
                "signal_id": signal_id,
                "tier": tier,
                "routed": False,
                "destination": "mattermost",
                "skipped_reason": "tier_c_deferred",
                "webhook_status": "skipped",
            }
            self._append_audit_log(decision)
            return decision

        try:
            sent = self._post_to_mattermost(triage_payload)
        except urllib_error.HTTPError:
            # Let HTTPError bubble through so callers can distinguish
            # timeout-like conditions (504) from transient failures.
            raise
        except urllib_error.URLError:
            sent = False

        decision = {
            "timestamp": self._utc_now_iso(),
            "action": "route_to_triage",
            "signal_id": signal_id,
            "tier": tier,
            "routed": bool(sent),
            "destination": "mattermost",
            "webhook_status": "ok" if sent else "failed",
        }
        self._append_audit_log(decision)
        return decision
