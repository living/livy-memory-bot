#!/usr/bin/env python3
"""
feedback_collector.py — Collects Lincoln's feedback signals from feedback-log.jsonl.
Priority: 4 (quartenária — learning only, not auto-apply)

Reads: memory/feedback-log.jsonl
Maps: thumbs_down → correction signal; thumbs_up → positive reinforcement
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_bus import SignalEvent

FEEDBACK_LOG = Path(__file__).resolve().parents[1] / "memory" / "feedback-log.jsonl"


class FeedbackCollector:
    source = "feedback"
    priority = 4

    def collect(self, limit: int = 50) -> list[SignalEvent]:
        """Read last N feedback entries, emit correction signals for thumbs_down."""
        signals = []
        if not FEEDBACK_LOG.exists():
            return signals

        lines = FEEDBACK_LOG.read_text().strip().splitlines()
        for line in lines[-limit:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            action = entry.get("action", "")
            thumbs_down = entry.get("thumbs_down", 0)
            thumbs_up = entry.get("thumbs_up", 0)
            timestamp = entry.get("timestamp", "")

            if thumbs_down > thumbs_up:
                # Negative feedback → correction signal
                sig = SignalEvent(
                    source="feedback",
                    priority=4,
                    topic_ref=action if action.endswith(".md") else None,
                    signal_type="correction",
                    payload={
                        "description": f"Feedback negativo: {action}",
                        "evidence": f"feedback-log:{timestamp}",
                        "confidence": 0.9,
                    },
                    origin_id=f"feedback-{timestamp}",
                    origin_url=None,
                )
                signals.append(sig)

        return signals
