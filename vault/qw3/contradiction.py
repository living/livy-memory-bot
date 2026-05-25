"""
QW-3 — Contradiction detection for QW-2 decisions.

Detects conflicting decisions in the same topic file.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

# Negation patterns that indicate opposing decisions
NEGATION_PATTERNS = [
    r"\bn[ãa]o\b",
    r"\bnot\b",
    r"\bnever\b",
    r"\bdo not\b",
    r"\bdoes not\b",
    r"\bdon't\b",
    r"\bwon't\b",
    r"\bstop\b",
    r"\bremove\b",
    r"\bdesativar\b",
    r"\breverter\b",
    r"\breject\b",
    r"\bdeleting\b",
    r"\bdelete\b",
    r"\bremovendo\b",
    r"\bnunca\b",
    r"\bremover\b",
    r"\bremovido\b",
    r"\bnão\b",
    r"\bnão\b",  # alternate encoding
    r"\bdelete\b",
    r"\bdeleting\b",
]

# Affirmative patterns that indicate supportive decisions
AFFIRMATIVE_PATTERNS = [
    r"\bsim\b",
    r"\byes\b",
    r"\bdo\b",
    r"\bfazer\b",
    r"\bfaz\b",  # stem of fazer
    r"\bimplementar\b",
    r"\badicionar\b",
    r"\bcriar\b",
    r"\badd\b",
    r"\bcreate\b",
    r"\benable\b",
    r"\bativar\b",
    r"\bdeploy\b",
    r"\bmigrate\b",
    r"\busar\b",
    r"\buse\b",
    r"\baprovar\b",
    r"\bapprove\b",
    r"\bmanter\b",
    r"\bkept\b",
    r"\bkeep\b",
    r"\bacelerar\b",
    r"\benable\b",
]


@dataclass
class Contradiction:
    existing_ref: str
    new_ref: str
    severity: str  # "low" | "medium" | "high"
    reason: str
    existing_text: str
    new_text: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "existing_ref": self.existing_ref,
            "new_ref": self.new_ref,
            "severity": self.severity,
            "reason": self.reason,
            "existing_text": self.existing_text[:100],
            "new_text": self.new_text[:100],
        }


def _has_negation(text: str) -> bool:
    text = text.lower()
    for pattern in NEGATION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _has_affirmation(text: str) -> bool:
    text = text.lower()
    for pattern in AFFIRMATIVE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def _extract_topic_keywords(text: str) -> set[str]:
    """Extract key action nouns from decision text to find related decisions."""
    # Remove common prefixes
    text = re.sub(r"^(feat|fix|chore|ci|docs|style|refactor|test|perf)\s*:\s*", "", text, flags=re.IGNORECASE)
    # Extract meaningful words (length >= 3, keeping short negation/affirmation words)
    words = re.findall(r"\b[a-záéíóúàèìòùâêîôûãõäëïöüç-]{3,}\b", text.lower())
    # Also extract 2-char negation words (não, sim) that matter for contradiction
    short_words = re.findall(r"\b(?:n[ãa]o|sim|no|yes)\b", text.lower())
    words.extend(short_words)
    # Filter out common stopwords but keep short negation/affirmation words
    stopwords = {
        "that", "this", "with", "from", "have", "been", "were", "they",
        "their", "which", "will", "would", "could", "should", "when",
        "where", "what", "como", "para", "mais", "ainda", "também",
        "pode", "ser", "que", "uma", "está", "esse", "essa", "isso",
        "texto", "text", "title", "description", "using", "through",
        "this", "with", "from", "have", "been", "were", "they",
    }
    return set(w for w in words if w not in stopwords)


def detect_contradiction(new_decision: dict[str, Any], existing_decisions: list[dict[str, Any]]) -> list[Contradiction]:
    """
    Detect contradictions between a new decision and existing ones in the same topic.

    A contradiction is detected when:
    1. The new decision has an affirmation pattern and an existing one has negation (or vice versa)
    2. They share at least one topic keyword
    3. The decisions are from different sources or different dates

    Parameters
    ----------
    new_decision : dict with keys text, source_ref, date, source, confidence
    existing_decisions : list of similar dicts

    Returns
    -------
    list of Contradiction objects (may be empty)
    """
    contradictions = []
    new_text = new_decision.get("text", "")
    new_ref = new_decision.get("source_ref", "unknown")
    new_date = new_decision.get("date", "")
    new_confidence = new_decision.get("confidence", 0.5)

    new_has_neg = _has_negation(new_text)
    new_has_aff = _has_affirmation(new_text)

    # No contradiction possible if new decision has neither pattern
    if not new_has_neg and not new_has_aff:
        return []

    new_keywords = _extract_topic_keywords(new_text)

    for existing in existing_decisions:
        existing_ref = existing.get("source_ref", "")
        existing_text = existing.get("text", "")
        existing_date = existing.get("date", "")
        existing_confidence = existing.get("confidence", 0.5)

        # Skip same decision
        if existing_ref == new_ref:
            continue

        # Skip if same date and same source
        if existing_date == new_date and existing.get("source") == new_decision.get("source"):
            continue

        existing_has_neg = _has_negation(existing_text)
        existing_has_aff = _has_affirmation(existing_text)

        # Check for opposing signals
        opposing = (new_has_neg and existing_has_aff) or (new_has_aff and existing_has_neg)
        if not opposing:
            continue

        # Check keyword overlap
        existing_keywords = _extract_topic_keywords(existing_text)
        overlap = new_keywords & existing_keywords
        if not overlap:
            continue

        # Calculate severity based on confidence
        avg_conf = (new_confidence + existing_confidence) / 2.0
        if avg_conf < 0.5:
            severity = "low"
        elif avg_conf < 0.75:
            severity = "medium"
        else:
            severity = "high"

        reason = f"oposição: '{new_text[:40]}' vs '{existing_text[:40]}' — overlap: {overlap}"

        contradictions.append(Contradiction(
            existing_ref=existing_ref,
            new_ref=new_ref,
            severity=severity,
            reason=reason,
            existing_text=existing_text,
            new_text=new_text,
        ))

    return contradictions


def check_topic_for_contradictions(topic_entries: list[dict[str, Any]]) -> list[Contradiction]:
    """
    Check all entries in a topic file for internal contradictions.
    Returns list of detected contradictions.
    """
    all_contradictions = []
    for i, entry in enumerate(topic_entries):
        others = topic_entries[:i] + topic_entries[i+1:]
        contrs = detect_contradiction(entry, others)
        all_contradictions.extend(contrs)
    return all_contradictions
