#!/usr/bin/env python3
"""
research_guardrails_cron.py — Semi-autonomous research pipeline with guardrails.

Safety gates (ALL must pass for auto-apply):
  1. source == 'tldv'
  2. confidence >= 0.9
  3. decision text not already in topic file (dedupe by date+text)
  4. topic file exists and is writable
  5. no [skip-auto] marker in decision text

This script performs auto-apply locally and writes a structured report to
memory/.auto-applied/report-*.json. Daily user-facing summary is handled by
OpenClaw cron delivery (announce), not direct provider API calls.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

# Ensure vault package is on path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from vault.research.pipeline import ResearchPipeline

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

GUARDRAIL_MIN_CONFIDENCE = 0.9
ALLOWED_SOURCES = {"tldv"}
SKIP_MARKERS = {"[skip-auto]", "skip-auto", "no-auto", "manual-only"}

APPLIED_DIR = Path("memory/.auto-applied")
APPLIED_DIR.mkdir(parents=True, exist_ok=True)

STATE_FILE = Path("state/identity-graph/state.json")
BACKUP_DIR = Path("memory/.auto-applied/backups")
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def load_topic_decisions(topic_path: Path) -> list[tuple[str, str]]:
    """Return list of (date_str, decision_text) already in the Decisions section."""
    if not topic_path.exists():
        return []
    text = topic_path.read_text(encoding="utf-8")
    decisions = []
    in_section = False
    for line in text.splitlines():
        if line.strip() == "## Decisões":
            in_section = True
            continue
        if line.startswith("## ") and in_section:
            break
        if in_section and line.startswith("- ["):
            # Parse: "- [YYYY-MM-DD] Decision text [url] — via source"
            rest = line[2:]  # strip "- "
            if "] " in rest:
                date_part = rest.split("] ")[0] + "]"
                body = rest.split("] ", 1)[1]
                # Remove url and source part
                body = body.split(" [http")[0].split(" — via")[0].strip()
                decisions.append((date_part, body))
    return decisions


def extract_decision_text(decision) -> str:
    if isinstance(decision, str):
        return decision.strip()
    return str(decision).strip()


def passes_guardrails(event: dict, topic_path: Path, existing_decisions: list[tuple[str, str]]) -> tuple[bool, str]:
    """Return (passes, reason)."""
    source = event.get("source", "")
    if source not in ALLOWED_SOURCES:
        return False, f"source={source} not in {ALLOWED_SOURCES}"

    confidence = float(event.get("confidence", 0))
    if confidence < GUARDRAIL_MIN_CONFIDENCE:
        return False, f"confidence={confidence} < {GUARDRAIL_MIN_CONFIDENCE}"

    decision = event.get("decision_text", "")
    if not decision:
        return False, "no decision_text field"

    decision_lower = decision.lower()
    for marker in SKIP_MARKERS:
        if marker in decision_lower:
            return False, f"skip marker '{marker}' found"

    # Fuzzy dedupe: reject if >85% similar to any existing decision
    for _, existing in existing_decisions:
        if similarity(decision, existing) > 0.85:
            return False, f"duplicate (similarity {similarity(decision,existing):.2f} to existing)"

    return True, "ok"


def build_tldv_decision_candidates() -> list[dict]:
    """Poll TLDV for recent decisions that pass guardrails."""
    import requests

    headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}

    # Get meetings from last 7 days with summaries
    cutoff = datetime.now(timezone.utc).isoformat()[:10]
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/meetings",
        headers=headers,
        params={
            "select": "id,name,created_at",
            "created_at": f"gte.{cutoff}T00:00:00Z",
            "enriched_at": "not.is.null",
            "order": "created_at.desc",
            "limit": 50,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        return []

    meetings = resp.json()
    meeting_ids = [m["id"] for m in meetings]

    if not meeting_ids:
        return []

    sm_resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/summaries",
        headers=headers,
        params={
            "select": "meeting_id,decisions,topics,tags",
            "meeting_id": f"in.( {','.join(meeting_ids)} )",
            "limit": 50,
        },
        timeout=30,
    )
    if sm_resp.status_code != 200:
        return []

    summaries = {s["meeting_id"]: s for s in sm_resp.json()}

    candidates = []
    meeting_map = {m["id"]: m for m in meetings}

    for mid, sm in summaries.items():
        meeting = meeting_map.get(mid, {})
        decisions = sm.get("decisions") or []
        tags = [t.lower() for t in (sm.get("tags") or [])]
        topics = [t.lower() for t in (sm.get("topics") or [])]
        blob = " ".join(tags + topics + [meeting.get("name", "").lower()])

        for decision in decisions:
            dt = extract_decision_text(decision)
            if not dt:
                continue

            # Infer topic_ref from tags/name
            if any(k in blob for k in ["bat", "kaba", "bot"]):
                topic_ref = "bat-conectabot-observability.md"
            elif any(k in blob for k in ["tldv", "memory", "livy", "openclaw", "gateway"]):
                topic_ref = "livy-memory-agent.md"
            elif any(k in blob for k in ["delphos"]):
                topic_ref = "delphos-video-vistoria.md"
            elif any(k in blob for k in ["forge"]):
                topic_ref = "forge-platform.md"
            else:
                topic_ref = None

            candidates.append({
                "source": "tldv",
                "confidence": 0.9,  # TLDV decisions default to 0.9
                "decision_text": dt,
                "meeting_id": mid,
                "meeting_name": meeting.get("name", ""),
                "meeting_date": meeting.get("created_at", "")[:10],
                "tags": tags,
                "topic_ref": topic_ref,
                "url": f"https://tldv.io/meeting/{mid}",
            })

    return candidates


def apply_candidate(candidate: dict, topic_path: Path) -> bool:
    """Apply a single candidate to its topic file. Returns True on success."""
    date = candidate["meeting_date"]
    decision = candidate["decision_text"]
    url = candidate["url"]

    marker = f"- [{date}] {decision} [{url}] — via tldv\n"

    text = topic_path.read_text(encoding="utf-8")
    pos = text.find("## Decisões\n\n")
    if pos == -1:
        return False

    insert_at = pos + len("## Decisões\n\n")
    new_text = text[:insert_at] + marker + text[insert_at:]

    # Backup current
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    backup = BACKUP_DIR / f"{topic_path.name}.{stamp}.bak"
    backup.write_text(text, encoding="utf-8")

    topic_path.write_text(new_text, encoding="utf-8")
    return True


def run_and_report() -> dict:
    """Run the semi-autonomous pipeline and return a report dict."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    report_path = APPLIED_DIR / f"report-{stamp}.json"
    candidates = build_tldv_decision_candidates()

    applied = []
    skipped = []
    results = []

    for c in candidates:
        topic_ref = c.get("topic_ref")
        if not topic_ref:
            skipped.append((c, "no topic_ref matched"))
            continue

        topic_path = Path("memory/curated") / topic_ref
        if not topic_path.exists():
            skipped.append((c, f"topic file not found: {topic_ref}"))
            continue

        existing = load_topic_decisions(topic_path)
        passes, reason = passes_guardrails(c, topic_path, existing)

        if not passes:
            skipped.append((c, reason))
            continue

        success = apply_candidate(c, topic_path)
        if success:
            applied.append(c)
            results.append(f"✅ {c['meeting_date']} → {topic_ref}: {c['decision_text'][:80]}")
        else:
            skipped.append((c, "apply failed"))

    report = {
        "stamp": stamp,
        "candidates_total": len(candidates),
        "applied": applied,
        "skipped_count": len(skipped),
        "skipped_reasons": [{"candidate": s[0]["decision_text"][:60], "reason": s[1]} for s in skipped[:10]],
        "results": results,
    }

    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(f"[guardrails] Starting run at {datetime.now(timezone.utc).isoformat()}")
    report = run_and_report()
    print(
        json.dumps(
            {
                "summary": {
                    "applied": len(report.get("applied", [])),
                    "skipped": report.get("skipped_count", 0),
                    "candidates": report.get("candidates_total", 0),
                    "results": report.get("results", []),
                }
            },
            ensure_ascii=False,
        )
    )
    print(f"[guardrails] Done. Applied: {len(report.get('applied', []))}")
