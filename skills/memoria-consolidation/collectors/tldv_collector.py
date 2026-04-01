#!/usr/bin/env python3
"""
tldv_collector.py — Collects decisions and topics from TLDV via Supabase REST API.
Priority: 1 (primary — direction)

Schema confirmed (2026-04-01):
- meetings: id, name, created_at, enriched_at, source, enrichment_context
- summaries: meeting_id, topics, decisions, tags, raw_text, model_used
  (action_items, status_changes, consensus_topics: NOT AVAILABLE — error 42703)

Topic matching rules:
  BAT / ConectaBot → bat-conectabot-observability.md
  Forge            → forge-platform.md
  Delphos          → delphos-video-vistoria.md
  TLDV / meetings  → tldv-pipeline-state.md
  Memory / agent   → livy-memory-agent.md
  OpenClaw / gateway → openclaw-gateway.md
  default          → None (no automatic topic_ref)
"""
import os, requests
from datetime import datetime, timezone
from typing import Optional

# Import from signal_bus (sibling module)
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from signal_bus import SignalEvent, SignalBus

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

TOPIC_MAPPING = {
    "bat": "bat-conectabot-observability.md",
    "conectabot": "bat-conectabot-observability.md",
    "forge": "forge-platform.md",
    "delphos": "delphos-video-vistoria.md",
    "tldv": "tldv-pipeline-state.md",
    "memory": "livy-memory-agent.md",
    "openclaw": "openclaw-gateway.md",
    "gateway": "openclaw-gateway.md",
    "livy": "livy-memory-agent.md",
}


def match_topic(topics: list[str]) -> Optional[str]:
    """Match the first available topic file based on topic keywords."""
    for topic in topics:
        topic_lower = topic.lower()
        for keyword, topic_file in TOPIC_MAPPING.items():
            if keyword in topic_lower:
                return topic_file
    return None


def build_tldv_signal(
    summary_row: dict,
    meeting_url: Optional[str],
    participant_names: Optional[list[str]] = None,
) -> SignalEvent:
    """
    Build a SignalEvent from a TLDV summary row.
    decisions[] → one signal per decision (signal_type=decision)
    topics[] → used for topic_ref matching
    participant_names can be passed as third arg OR embedded in summary_row.
    """
    meeting_id = summary_row.get("meeting_id", "")
    decisions = summary_row.get("decisions") or []
    topics = summary_row.get("topics") or []
    topic_ref = match_topic(topics)

    # participant_names can come from explicit arg OR from summary_row
    names = participant_names or summary_row.get("participant_names") or []
    # Robert as participant = explicit direction, max confidence
    is_robert = any("robert" in p.lower() for p in names)
    confidence = 1.0 if is_robert else 0.8

    signals = []
    for decision in decisions:
        desc = decision if isinstance(decision, str) else str(decision)
        if not desc:
            continue
        signal = SignalEvent(
            source="tldv",
            priority=1,
            topic_ref=topic_ref,
            signal_type="decision",
            payload={
                "description": desc,
                "evidence": meeting_url,
                "confidence": confidence,
            },
            origin_id=meeting_id,
            origin_url=meeting_url,
        )
        signals.append(signal)

    # If no decisions but topics exist, emit a topic_mentioned signal
    if not signals and topics:
        signal = SignalEvent(
            source="tldv",
            priority=1,
            topic_ref=topic_ref,
            signal_type="topic_mentioned",
            payload={
                "description": f"Tópicos mencionados: {', '.join(topics[:5])}",
                "evidence": meeting_url,
                "confidence": 0.6,
            },
            origin_id=meeting_id,
            origin_url=meeting_url,
        )
        signals.append(signal)

    # Return first signal (caller can iterate if needed)
    return signals[0] if signals else None


class TLDVCollector:
    """
    Collects TLDV decisions and topics via Supabase REST API.
    Fetches meetings with summaries since last run (tracked via cursor file).
    """
    source = "tldv"
    priority = 1

    def __init__(self, supabase_url: Optional[str] = None, supabase_key: Optional[str] = None):
        self.supabase_url = supabase_url or SUPABASE_URL
        self.supabase_key = supabase_key or SUPABASE_KEY
        self.base_url = f"{self.supabase_url}/rest/v1"
        self.headers = {
            "apikey": self.supabase_key,
            "Authorization": f"Bearer {self.supabase_key}",
            "Content-Type": "application/json",
        }

    def _get(self, table: str, params: Optional[dict] = None) -> list:
        """Execute GET request to Supabase REST API."""
        url = f"{self.base_url}/{table}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json() or []

    def fetch_meetings_since(self, cursor: Optional[str] = None) -> list[dict]:
        """
        Fetch meetings since cursor (ISO timestamp).
        Returns list of meeting dicts with id, created_at, enriched_at.
        """
        params = {
            "select": "id,name,created_at,enriched_at,source",
            "order": "created_at.desc",
            "limit": 50,
        }
        if cursor:
            params["created_at"] = f"gt.{cursor}"
        meetings = self._get("meetings", params)
        return [m for m in meetings if m.get("enriched_at")]  # only enriched

    def fetch_summary(self, meeting_id: str) -> Optional[dict]:
        """Fetch summary row for a given meeting_id."""
        results = self._get(
            "summaries",
            params={"meeting_id": f"eq.{meeting_id}", "limit": 1}
        )
        return results[0] if results else None

    def collect(self, cursor: Optional[str] = None) -> list[SignalEvent]:
        """
        Main entry point: collect all signals from TLDV since cursor.
        Returns list of SignalEvents.
        """
        meetings = self.fetch_meetings_since(cursor)
        signals = []
        for meeting in meetings:
            summary = self.fetch_summary(meeting["id"])
            if not summary:
                continue
            # Check participants via enrichment_context if available
            participant_names = None
            # Emit decision signals
            for decision in (summary.get("decisions") or []):
                sig = build_tldv_signal(
                    summary,
                    meeting_url=f"https://tldv.io/meeting/{meeting['id']}",
                    participant_names=participant_names,
                )
                if sig:
                    sig.topic_ref = sig.topic_ref or match_topic(summary.get("topics") or [])
                    signals.append(sig)
            # Emit topic_mentioned if no decisions
            if not (summary.get("decisions") or []):
                sig = build_tldv_signal(summary, f"https://tldv.io/meeting/{meeting['id']}")
                if sig:
                    signals.append(sig)
        return signals
