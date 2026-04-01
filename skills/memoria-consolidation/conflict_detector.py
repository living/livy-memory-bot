#!/usr/bin/env python3
"""
conflict_detector.py — Detects conflicts between signals from different sources.
A conflict = TLDV says "X is the direction" BUT logs or Git shows "X failed/was abandoned".

Rules:
  - decision (TLDV, priority 1) vs failure (logs, priority 2) → CONFLICT
  - decision (TLDV, priority 1) vs correction (Git, priority 3) → CONFLICT
  - success (logs) + decision (TLDV) → no conflict (they agree)
  - Two decisions from TLDV → no conflict (same source, no contradiction)
"""
from dataclasses import dataclass
from typing import Optional

from signal_bus import SignalEvent


@dataclass
class Conflict:
    """Represents a detected conflict between two signals."""
    topic: str
    primary_signal: SignalEvent      # the directional signal (usually TLDV)
    conflicting_signal: SignalEvent  # the contradicting signal (logs/Git)
    proposal: str                    # suggested resolution


class ConflictDetector:
    """
    Detects conflicts between signals based on source and signal type.
    Conflict rule: decision (TLDV) vs (failure OR correction) from other sources.
    """

    def detect(
        self, signals: list[SignalEvent], topic_states: dict
    ) -> list[Conflict]:
        """
        Given all signals for a curation cycle, detect conflicts.
        Returns list of Conflict objects.
        """
        conflicts = []

        # Group by topic
        by_topic: dict[str, list[SignalEvent]] = {}
        for sig in signals:
            if sig.topic_ref:
                by_topic.setdefault(sig.topic_ref, []).append(sig)

        for topic, topic_sigs in by_topic.items():
            conflict = self._check_topic(topic, topic_sigs)
            if conflict:
                conflicts.append(conflict)

        return conflicts

    def _check_topic(self, topic: str, signals: list[SignalEvent]) -> Optional[Conflict]:
        """Check a single topic for conflicts."""
        tldv_decisions = [s for s in signals if s.source == "tldv" and s.signal_type == "decision"]
        tldv_signals = [s for s in signals if s.source == "tldv"]

        # Primary signal: first TLDV decision (the "direction")
        primary = tldv_decisions[0] if tldv_decisions else (tldv_signals[0] if tldv_signals else None)
        if not primary:
            return None

        # Conflicting signals: failure from logs OR correction from Git
        for sig in signals:
            if sig.source == "logs" and sig.signal_type == "failure":
                # Check if the failure is related to the same thing TLDV decided
                if self._is_related(primary, sig):
                    return Conflict(
                        topic=topic,
                        primary_signal=primary,
                        conflicting_signal=sig,
                        proposal=self._make_proposal(primary, sig),
                    )
            if sig.source == "github" and sig.signal_type == "correction":
                if self._is_related(primary, sig):
                    return Conflict(
                        topic=topic,
                        primary_signal=primary,
                        conflicting_signal=sig,
                        proposal=self._make_proposal(primary, sig),
                    )

        return None

    def _is_related(self, sig1: SignalEvent, sig2: SignalEvent) -> bool:
        """Check if two signals are about the same subject."""
        desc1 = sig1.payload.get("description", "").lower()
        desc2 = sig2.payload.get("description", "").lower()
        # Simple keyword overlap check
        words1 = set(desc1.split())
        words2 = set(desc2.split())
        # Remove common stopwords
        stopwords = {"para", "usar", "com", "o", "a", "de", "e", "em", "que", "é"}
        kw1 = words1 - stopwords
        kw2 = words2 - stopwords
        return bool(kw1 & kw2)  # any keyword overlap = related

    def _make_proposal(self, primary: SignalEvent, conflicting: SignalEvent) -> str:
        """Generate a resolution proposal based on signals."""
        primary_desc = primary.payload.get("description", "")[:50]
        conf_desc = conflicting.payload.get("description", "")[:50]
        return (f"Revisar: '{primary_desc}' vs evidência de falha: '{conf_desc}'. "
                f"Fonte primária: {primary.source}. "
                f"Verificar antes de fechar topic.")