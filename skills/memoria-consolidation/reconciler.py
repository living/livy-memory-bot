#!/usr/bin/env python3
"""
reconciler.py — Reconcile current topic state against concrete evidence.

Rules:
  R002 — Meeting-only claim (tldv only) is deferred for operational confirmation.
  R004 — Bug marked resolved in meeting + confirmed by concrete evidence (github/logs)
         moves to history section, not erasure.
  R003 — Architectural decision from meeting alone is deferred.
  R005 — New issue discovered in concrete evidence (not in any section) is flagged
         as deferred/new for manual triage.
"""
from collections import defaultdict
from decision_ledger import DecisionRecord

RULE_MEETING_NEEDS_CONFIRMATION = "R002_meeting_claim_needs_operational_confirmation"
RULE_RESOLVED_BUG_HISTORY = "R004_resolved_bug_moves_to_history_not_erasure"
RULE_ADVISORY_DECISION_DEFERRED = "R003_advisory_decision_deferred"
RULE_NEW_ISSUE_FLAGGED = "R005_new_issue_flagged_for_triage"


def _slug_from_title(title: str) -> str:
    """Mirror the slugification used in curation_cron.py when building current_state."""
    return title.lower().replace(" ", "-").replace(":", "")[:40]


def _title_words(title: str) -> set[str]:
    """Return meaningful words from a title for fuzzy overlap matching."""
    return {w.strip(".,;:()[]{}") for w in title.lower().split() if len(w) > 2}


def _fuzzy_match(entity_key: str, open_issues: list[dict]) -> dict | None:
    """
    Check if entity_key (from evidence) matches any open issue via fuzzy title overlap.
    entity_key format: "decision:<slug>" or "issue:<slug>"

    Returns the matched open_issue dict or None.
    Uses multi-word overlap: at least 2 significant words must match.
    """
    slug = entity_key.split(":", 1)[1] if ":" in entity_key else entity_key
    sig_words = _title_words(slug.replace("-", " "))

    if len(sig_words) < 2:
        # Too short for reliable fuzzy match — also check exact prefix
        for issue in open_issues:
            issue_slug = issue["key"].split(":", 1)[1] if ":" in issue["key"] else ""
            if slug.startswith(issue_slug[:20]) or issue_slug.startswith(slug[:20]):
                return issue
        return None

    best: dict | None = None
    best_score = 0
    for issue in open_issues:
        issue_words = _title_words(issue.get("title", "").replace("-", " "))
        score = len(sig_words & issue_words)
        if score >= 2 and score > best_score:
            best = issue
            best_score = score
    return best


def reconcile_topic(topic: str, current_state: dict, evidence_items: list) -> list[DecisionRecord]:
    by_entity = defaultdict(list)
    for item in evidence_items:
        by_entity[item.entity_key].append(item)

    decisions = []
    open_issues = current_state.get("open_issues", [])
    resolved_issues = current_state.get("resolved_issues", [])

    open_keys = {issue["key"] for issue in open_issues}
    resolved_keys = {issue["key"] for issue in resolved_issues}

    for entity_key, items in by_entity.items():
        sources = {item.source for item in items}
        refs = [item.evidence_ref for item in items if item.evidence_ref]

        # ── Case 1: entity_key matched exactly in open_issues ─────────────
        if entity_key in open_keys:
            _emit_open_to_resolved(topic, entity_key, items, sources, refs, decisions)
            continue

        # ── Case 2: fuzzy title-overlap match with open_issues ────────────
        matched_issue = _fuzzy_match(entity_key, open_issues)
        if matched_issue is not None:
            _emit_open_to_resolved(topic, matched_issue["key"], items, sources, refs, decisions)
            continue

        # ── Case 3: entity_key already resolved — no-op (preserve history) ─
        if entity_key in resolved_keys:
            continue  # already handled, do nothing

        # ── Case 4: entity is a "decision" type from meeting only — defer ─
        if sources == {"tldv"}:
            decisions.append(DecisionRecord(
                topic=topic,
                entity_key=entity_key,
                entity_type="decision",
                old_status=None,
                new_status="deferred",
                why="Meeting-only claim — awaiting operational confirmation before acting.",
                rule_id=RULE_ADVISORY_DECISION_DEFERRED,
                confidence=0.7,
                result="deferred",
                evidence_refs=refs,
                observed_at=items[-1].observed_at,
            ))
            continue

        # ── Case 5: new issue not in any section — flag for triage ───────
        decisions.append(DecisionRecord(
            topic=topic,
            entity_key=entity_key,
            entity_type="issue",
            old_status=None,
            new_status="new",
            why="Issue referenced in evidence but not found in open or resolved sections.",
            rule_id=RULE_NEW_ISSUE_FLAGGED,
            confidence=0.6,
            result="deferred",
            evidence_refs=refs,
            observed_at=items[-1].observed_at,
        ))

    return decisions


def _emit_open_to_resolved(
    topic: str,
    entity_key: str,
    items,
    sources: set[str],
    refs: list[str],
    decisions: list,
) -> None:
    """
    Emit a decision for an entity that matched an open issue.
    - tldv only → deferred (R002)
    - tldv + github/logs → accepted, resolved (R004)
    """
    if sources == {"tldv"}:
        decisions.append(DecisionRecord(
            topic=topic,
            entity_key=entity_key,
            entity_type="issue",
            old_status="open",
            new_status="open",
            why="Meeting-only claim is not enough to change operational status.",
            rule_id=RULE_MEETING_NEEDS_CONFIRMATION,
            confidence=0.7,
            result="deferred",
            evidence_refs=refs,
            observed_at=items[-1].observed_at,
        ))
    elif "tldv" in sources and ("github" in sources or "logs" in sources):
        decisions.append(DecisionRecord(
            topic=topic,
            entity_key=entity_key,
            entity_type="issue",
            old_status="open",
            new_status="resolved",
            why="Meeting claim was confirmed by concrete non-memory evidence.",
            rule_id=RULE_RESOLVED_BUG_HISTORY,
            confidence=0.95,
            result="accepted",
            evidence_refs=refs,
            observed_at=items[-1].observed_at,
        ))
    elif "github" in sources or "logs" in sources:
        # Concrete evidence alone — still accept (runtime/runtime wins)
        decisions.append(DecisionRecord(
            topic=topic,
            entity_key=entity_key,
            entity_type="issue",
            old_status="open",
            new_status="resolved",
            why="Concrete evidence confirms this issue is resolved.",
            rule_id="R001_concrete_evidence_beats_memory",
            confidence=0.9,
            result="accepted",
            evidence_refs=refs,
            observed_at=items[-1].observed_at,
        ))
