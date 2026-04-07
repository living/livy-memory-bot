#!/usr/bin/env python3
"""
curation_cron.py — Orchestrates the full signal curation pipeline.

Flow:
  1. Generate correlation_id
  2. Collect signals from all sources (TLDV primary)
  3. Group signals by topic_ref
  4. Persist events to signal-events.jsonl
  5. Reconciliation (shadow or write mode, TLDV pilot)
  6. Analyze each topic file → candidate changes
  7. Auto-curate (apply when conditions met)
  8. Log to memory/logs/curation-{date}.log (JSON Lines)
  9. Write curation log
  10. Send Telegram summary

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — TLDV
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID — notifications
  CURATED_DIR — path to memory/curated/ (default: same dir as script)
  RECONCILIATION_WRITE_MODE — set to "1" to promote TLDV pilot to write mode
"""
import json, logging, sys, uuid
from datetime import datetime, timezone
from pathlib import Path

# Setup structured JSON logging to stdout (captured by cron wrapper)
logging.basicConfig(
    level=logging.INFO,
    format='{"level": "%(levelname)s", "ts": "%(asctime)sZ", "message": "%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("curation")

BASE_DIR = Path(__file__).resolve().parents[2]  # workspace-livy-memory/ (up from collectors/ and skills/)
MEMORY_DIR = BASE_DIR / "memory"
CURATED_DIR = MEMORY_DIR / "curated"
LOGS_DIR = MEMORY_DIR / "logs"
SIGNAL_EVENTS_FILE = MEMORY_DIR / "signal-events.jsonl"
CURATION_LOG_FILE = MEMORY_DIR / "curation-log.md"
RECONCILIATION_LEDGER_FILE = MEMORY_DIR / "reconciliation-ledger.jsonl"
RECONCILIATION_REPORT_FILE = MEMORY_DIR / "reconciliation-report.md"

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)

import os
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-5158607302")

from signal_bus import SignalBus
from collectors.tldv_collector import TLDVCollector
from collectors.logs_collector import LogsCollector
from collectors.github_collector import GitHubCollector
from collectors.feedback_collector import FeedbackCollector
from topic_analyzer import TopicAnalyzer
from auto_curator import AutoCurator
from conflict_detector import ConflictDetector
from conflict_queue import ConflictQueue
from evidence_normalizer import normalize_signal_event
from fact_snapshot_builder import build_topic_snapshots
from reconciler import reconcile_topic
from decision_ledger import DecisionLedger
from topic_rewriter import parse_topic_file

RECONCILIATION_WRITE_MODE = os.environ.get("RECONCILIATION_WRITE_MODE", "0") == "1"


def log_structured(level: str, correlation_id: str, component: str, event: str, **kwargs):
    """Emit a structured JSON log line."""
    entry = {
        "level": level,
        "ts": datetime.now(timezone.utc).isoformat(),
        "correlation_id": correlation_id,
        "component": component,
        "event": event,
        **kwargs,
    }
    logger.log(getattr(logging, level), json.dumps(entry))


def send_telegram(message: str):
    """Send message via Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        print(f"[TELEGRAM] {message}")
        return
    import urllib.request
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    data = json.dumps({"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}).encode()
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


def format_curation_log_entry(correlation_id: str, topic: str, change_type: str,
                               description: str, evidence: str, auto: bool) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M BRT")
    auto_str = "Yes" if auto else "No"
    return f"""## {ts} · {correlation_id}

**topic:** {topic}
**auto:** {auto_str}
**change:** {change_type}
**description:** {description}
**evidence:** {evidence}
"""


def run_reconciliation_shadow_mode(correlation_id: str, topic_ref: str, topic_path: Path, events: list) -> dict:
    """
    Run the reconciliation pipeline in shadow mode for a single topic.
    - Normalizes signals into evidence items
    - Builds a fact snapshot
    - Reconciles against the topic's current state
    - Writes decisions to the ledger and a report
    - Does NOT modify the topic file
    """
    if not topic_path.exists():
        return {"topic": topic_ref, "mode": "shadow", "skipped": True, "reason": "file_not_found"}

    # Normalize all events and build topic snapshots via fact_snapshot_builder
    all_items = [normalize_signal_event(e) for e in events]
    all_snapshots = build_topic_snapshots(all_items)
    snapshot = all_snapshots.get(topic_ref)
    evidence_items = snapshot.evidence if snapshot else []

    # Build current state from topic file sections
    content = topic_path.read_text()
    parsed = parse_topic_file(content)

    open_issues = []
    resolved_issues = []

    open_section = parsed.sections.get("Issues Abertas", "")
    if open_section and open_section not in ("(nenhuma)", ""):
        for line in open_section.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                title = line.lstrip("-").strip().split("—")[0].strip()
                slug = title.lower().replace(" ", "-").replace(":", "")[:40]
                open_issues.append({"key": f"issue:{slug}", "title": title, "status": "open"})

    resolved_section = parsed.sections.get("Issues Resolvidas / Superadas", "")
    if resolved_section and resolved_section not in ("(nenhuma)", ""):
        for line in resolved_section.split("\n"):
            line = line.strip()
            if line.startswith("-"):
                title = line.lstrip("-").strip().split("—")[0].strip()
                slug = title.lower().replace(" ", "-").replace(":", "")[:40]
                resolved_issues.append({"key": f"issue:{slug}", "title": title, "status": "resolved"})

    current_state = {"open_issues": open_issues, "resolved_issues": resolved_issues}

    # Reconcile
    decisions = reconcile_topic(topic_ref, current_state, evidence_items)

    # Write to ledger
    if decisions:
        ledger = DecisionLedger(RECONCILIATION_LEDGER_FILE)
        ledger.append_many(decisions)

    # Write reconciliation report
    ts = datetime.now(timezone.utc).isoformat()
    accepted = [d for d in decisions if d.result == "accepted"]
    deferred = [d for d in decisions if d.result == "deferred"]
    causal_completeness = sum(d.confidence for d in decisions) / len(decisions) if decisions else 0.0

    report_lines = [
        f"# Reconciliation Report — {ts}",
        f"**correlation_id:** {correlation_id}",
        f"**topic:** {topic_ref}",
        f"**mode:** shadow",
        "",
        "## Decisions",
    ]
    for d in decisions:
        report_lines.append(f"- `{d.result}` | {d.entity_key} | {d.rule_id} | conf={d.confidence:.2f}")

    conflict_count = len([d for d in decisions if d.result == "conflict"])
    freshness_checked = topic_ref  # single-topic function

    report_lines.extend([
        "",
        f"**confirmed:** {len(accepted)}",
        f"**deferred:** {len(deferred)}",
        f"**conflicts:** {conflict_count}",
        f"**causal_completeness:** {causal_completeness:.2f}",
        f"**freshness_checked_topics:** {freshness_checked}",
        f"**run_mode:** shadow" if not RECONCILIATION_WRITE_MODE else f"**run_mode:** write",
    ])

    RECONCILIATION_REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RECONCILIATION_REPORT_FILE.write_text("\n".join(report_lines) + "\n")

    # Write mode: actually update the topic file
    # evidence_items already computed at top of function — no need to re-normalize
    if RECONCILIATION_WRITE_MODE and decisions:
        from topic_rewriter import render_topic_file as _render

        accepted_decisions = [d for d in decisions if d.result == "accepted"]
        if accepted_decisions:
            rendered = _render(parsed, accepted_decisions)
            apply_reconciliation_write_mode(topic_path, rendered)

    return {
        "topic": topic_ref,
        "mode": "shadow",
        "decisions": len(decisions),
        "accepted": len(accepted),
        "deferred": len(deferred),
        "causal_completeness": round(causal_completeness, 2),
    }


def apply_reconciliation_write_mode(topic_path: Path, rendered_content: str) -> None:
    """
    Safely write reconciled content to a topic file using atomic replace.
    1. Archive current version to memory/.archive/YYYYMMDDHHMM/
    2. Write to topic_path.tmp
    3. Atomically replace original
    """
    from datetime import datetime, timezone

    if not RECONCILIATION_WRITE_MODE:
        return  # Guard: do nothing unless write mode is explicitly enabled

    # Archive
    archive_dir = MEMORY_DIR / ".archive" / datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
    archive_dir.mkdir(parents=True, exist_ok=True)
    archived = archive_dir / topic_path.name
    archived.write_text(topic_path.read_text())

    # Atomic replace
    temp_path = topic_path.with_suffix(".tmp")
    temp_path.write_text(rendered_content)
    temp_path.replace(topic_path)


def main():
    correlation_id = str(uuid.uuid4())
    log_structured("INFO", correlation_id, "curation_cron", "cycle_started")

    bus = SignalBus()
    bus.start_cycle()

    curated_dir = CURATED_DIR

    # ── 1. Collect signals ────────────────────────────────────────────────
    log_structured("INFO", correlation_id, "curation_cron", "collecting_signals")

    tldv_collector = TLDVCollector()
    try:
        tldv_signals = tldv_collector.collect()
        log_structured("INFO", correlation_id, "tldv_collector", "collection_complete",
                        count=len(tldv_signals))
    except Exception as e:
        log_structured("ERROR", correlation_id, "tldv_collector", "collection_failed",
                        error=str(e), retryable=True)
        tldv_signals = []

    for sig in tldv_signals:
        bus.emit(sig)

    # Collect logs signals
    logs_collector = LogsCollector()
    try:
        logs_signals = logs_collector.collect()
        for sig in logs_signals:
            bus.emit(sig)
        log_structured("INFO", correlation_id, "logs_collector", "collection_complete",
                       count=len(logs_signals))
    except Exception as e:
        log_structured("ERROR", correlation_id, "logs_collector", "collection_failed",
                       error=str(e))

    # Collect GitHub signals
    github_collector = GitHubCollector()
    try:
        github_signals = github_collector.collect()
        for sig in github_signals:
            bus.emit(sig)
        log_structured("INFO", correlation_id, "github_collector", "collection_complete",
                       count=len(github_signals))
    except Exception as e:
        log_structured("ERROR", correlation_id, "github_collector", "collection_failed",
                       error=str(e))

    # Collect feedback signals
    feedback_collector = FeedbackCollector()
    try:
        feedback_signals = feedback_collector.collect()
        for sig in feedback_signals:
            bus.emit(sig)
        log_structured("INFO", correlation_id, "feedback_collector", "collection_complete",
                       count=len(feedback_signals))
    except Exception as e:
        log_structured("ERROR", correlation_id, "feedback_collector", "collection_failed",
                       error=str(e))

    # Detect conflicts
    conflict_detector = ConflictDetector()
    conflicts = conflict_detector.detect(bus.events, {})
    log_structured("INFO", correlation_id, "conflict_detector", "detection_complete",
                   count=len(conflicts))

    # Add conflicts to queue
    if conflicts:
        queue = ConflictQueue()
        for conflict in conflicts:
            queue.add(conflict)
        log_structured("WARN", correlation_id, "conflict_queue", "conflicts_added",
                       count=len(conflicts))

    log_structured("INFO", correlation_id, "signal_bus", "events_collected",
                    total=len(bus.events))

    # Group signals by topic_ref (used by both reconciliation and auto-curate)
    topics = set(e.topic_ref for e in bus.events if e.topic_ref)

    # ── 2. Persist signals to JSONL ──────────────────────────────────────
    bus.persist(SIGNAL_EVENTS_FILE, mode="append")
    log_structured("INFO", correlation_id, "signal_bus", "events_persisted",
                    path=str(SIGNAL_EVENTS_FILE), count=len(bus.events))

    # ── 3. Run reconciliation in shadow mode (TLDV pilot only) ─────────────
    reconciliation_topics = {"tldv-pipeline-state.md"}
    reconciliation_results = []

    for topic_ref in topics:
        if topic_ref not in reconciliation_topics:
            continue

        topic_path = curated_dir / topic_ref
        result = run_reconciliation_shadow_mode(
            correlation_id=correlation_id,
            topic_ref=topic_ref,
            topic_path=topic_path,
            events=bus.events,
        )
        reconciliation_results.append(result)
        log_structured("INFO", correlation_id, "reconciliation", "shadow_run_complete",
                        topic=topic_ref, mode="shadow", **result)

    if reconciliation_results:
        log_structured("INFO", correlation_id, "reconciliation", "pilot_complete",
                       topics=len(reconciliation_results))

    # ── 4. Analyze + Auto-curate per topic ───────────────────────────────
    analyzer = TopicAnalyzer()
    curator = AutoCurator()
    curation_log_lines = []
    applied_count = 0

    # Group signals by topic
    for topic_ref in topics:
        topic_path = curated_dir / topic_ref
        if not topic_path.exists():
            continue

        signals = bus.get_by_topic(topic_ref)
        candidates = analyzer.analyze(topic_path, signals)

        for candidate in candidates:
            if curator.should_apply(candidate):
                ok = curator.apply_change(topic_path, candidate)
                if ok:
                    applied_count += 1
                    log_structured("INFO", correlation_id, "auto_curator", "change_applied",
                                   topic=topic_ref, change_type=candidate.change_type,
                                   description=candidate.description[:80])
                    curation_log_lines.append(
                        format_curation_log_entry(
                            correlation_id, topic_ref,
                            candidate.change_type, candidate.description,
                            candidate.evidence or "", auto=True
                        )
                    )
            else:
                # Flag for Lincoln review (conflict or low confidence)
                log_structured("WARN", correlation_id, "auto_curator", "change_requires_review",
                               topic=topic_ref, change_type=candidate.change_type,
                               description=candidate.description[:80])
                curation_log_lines.append(
                    format_curation_log_entry(
                        correlation_id, topic_ref,
                        candidate.change_type, candidate.description,
                        candidate.evidence or "", auto=False
                    )
                )

    # ── 5. Write curation log ───────────────────────────────────────────
    if curation_log_lines:
        with CURATION_LOG_FILE.open("a") as f:
            f.write("\n".join(curation_log_lines) + "\n")

    # ── 6. Send Telegram summary ─────────────────────────────────────────
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    summary = f"""🧠 *Signal Curation — {ts}*

📊 Sinais: {len(bus.events)} | Temas: {len(topics)} | Aplicados: {applied_count}
🔗 correlation_id: `{correlation_id}`

"""
    if curation_log_lines:
        for line in curation_log_lines[:5]:  # first 5
            summary += line + "\n"
    else:
        summary += "✅ Nenhuma mudança necessária."

    send_telegram(summary)
    log_structured("INFO", correlation_id, "curation_cron", "cycle_complete",
                    signals=len(bus.events), topics=len(topics),
                    applied=applied_count)


if __name__ == "__main__":
    main()
