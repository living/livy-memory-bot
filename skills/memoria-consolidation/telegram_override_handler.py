"""Telegram override parser + audit logger for hold/promote actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_AUDIT_LOG_PATH = Path(__file__).resolve().parents[2] / "memory" / "triage-decisions.jsonl"


class TelegramOverrideHandler:
    def __init__(self, audit_log_path: str | Path | None = None) -> None:
        self.audit_log_path = Path(audit_log_path) if audit_log_path else DEFAULT_AUDIT_LOG_PATH

    def _utc_now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def _validate(self, action: str, signal_id: str, reason: str) -> None:
        if action not in {"hold", "promote"}:
            raise ValueError(f"Unknown override action: {action}")
        if not signal_id.strip():
            raise ValueError("signal_id is required")
        if not reason.strip():
            raise ValueError("reason is required")

    def parse_override(self, raw_text: str, override_type: str = "callback_data") -> dict[str, str]:
        raw_text = (raw_text or "").strip()

        if override_type == "callback_data":
            # Format: action:signal_id:reason (reason may contain colons)
            parts = raw_text.split(":")
            if len(parts) < 3:
                raise ValueError("Invalid callback_data format")
            action = parts[0].strip().lower()
            signal_id = parts[1].strip()
            reason = ":".join(parts[2:]).strip()
        elif override_type == "message_text":
            # Format: /override <action> <signal_id> <reason...>
            parts = raw_text.split()
            if len(parts) < 4 or parts[0] != "/override":
                raise ValueError("Invalid override message format")
            action = parts[1].strip().lower()
            signal_id = parts[2].strip()
            reason = " ".join(parts[3:]).strip()
        else:
            raise ValueError(f"Unknown override type: {override_type}")

        self._validate(action, signal_id, reason)
        return {
            "action": action,
            "signal_id": signal_id,
            "reason": reason,
            "override_type": override_type,
        }

    def _append_audit_log(self, record: dict[str, Any]) -> None:
        if str(self.audit_log_path) == ":memory:":
            return
        self.audit_log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.audit_log_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def apply_override(self, override: dict[str, Any]) -> dict[str, Any]:
        action = str(override.get("action", "")).strip().lower()
        signal_id = str(override.get("signal_id", "")).strip()
        reason = str(override.get("reason", "")).strip()
        override_type = str(override.get("override_type", "callback_data"))

        self._validate(action, signal_id, reason)

        record = {
            "timestamp": self._utc_now_iso(),
            "action": action,
            "signal_id": signal_id,
            "reason": reason,
            "override_type": override_type,
        }
        self._append_audit_log(record)

        return {
            "applied": True,
            "logged": True,
            "action": action,
            "signal_id": signal_id,
        }
