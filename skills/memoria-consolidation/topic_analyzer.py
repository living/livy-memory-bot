#!/usr/bin/env python3
"""
topic_analyzer.py — Analyzes a topic file against new signals and produces candidate changes.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from signal_bus import SignalEvent


@dataclass
class CandidateChange:
    """A proposed change to a topic file."""
    change_type: str  # "add_decision" | "update_entry" | "deprecate_entry" | "archive_entry"
    description: str
    evidence: Optional[str]
    signal_source: str


class TopicAnalyzer:
    """
    Given a topic file path + list of SignalEvents for that topic,
    compute the list of candidate changes.
    """

    def analyze(self, topic_path: Path, signals: list[SignalEvent]) -> list[CandidateChange]:
        """Analyze a topic file. Returns list of candidate changes."""
        if not topic_path.exists():
            return []
        content = topic_path.read_text()
        return self.analyze_content(topic_path.name, content, signals)

    def analyze_content(
        self, filename: str, content: str, signals: list[SignalEvent]
    ) -> list[CandidateChange]:
        """Analyze topic file content against signals."""
        candidates = []
        for sig in signals:
            if sig.topic_ref and sig.topic_ref not in filename:
                continue
            if sig.signal_type == "decision":
                change = self._handle_decision(content, sig)
                if change:
                    candidates.append(change)
            elif sig.signal_type == "failure":
                change = self._handle_failure(content, sig)
                if change:
                    candidates.append(change)
            elif sig.signal_type == "topic_mentioned":
                change = self._handle_topic_mentioned(content, sig)
                if change:
                    candidates.append(change)
        return candidates

    def _handle_decision(self, content: str, sig: SignalEvent) -> Optional[CandidateChange]:
        """If decision is new, propose add_decision."""
        desc = sig.payload.get("description", "")
        if not desc:
            return None
        # Check if decision already exists in content
        if desc in content:
            return None
        return CandidateChange(
            change_type="add_decision",
            description=desc,
            evidence=sig.payload.get("evidence"),
            signal_source=sig.source,
        )

    def _handle_failure(self, content: str, sig: SignalEvent) -> Optional[CandidateChange]:
        """Failure signal → propose deprecate_entry."""
        desc = sig.payload.get("description", "")
        evidence = sig.payload.get("evidence", "")
        return CandidateChange(
            change_type="deprecate_entry",
            description=f"{desc} (evidência: {evidence})",
            evidence=evidence,
            signal_source=sig.source,
        )

    def _handle_topic_mentioned(self, content: str, sig: SignalEvent) -> Optional[CandidateChange]:
        """Topic mentioned with high confidence → add to topics list if new."""
        # Only suggest if confidence is high and no existing decision covers it
        if sig.payload.get("confidence", 0) < 0.7:
            return None
        return None  # topic_mentioned alone is not enough for a change