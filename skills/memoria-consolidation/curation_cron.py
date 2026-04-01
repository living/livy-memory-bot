#!/usr/bin/env python3
"""
curation_cron.py — Orchestrates the full signal curation pipeline.

Flow:
  1. Generate correlation_id
  2. Collect signals from all sources (TLDV primary)
  3. Group signals by topic_ref
  4. Analyze each topic file → candidate changes
  5. Auto-curate (apply when conditions met)
  6. Persist events to signal-events.jsonl
  7. Log to memory/logs/curation-{date}.log (JSON Lines)
  8. Write curation-log.md
  9. Send Telegram summary

Environment:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY — TLDV
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID — notifications
  CURATED_DIR — path to memory/curated/ (default: same dir as script)
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

BASE_DIR = Path(__file__).resolve().parents[1]  # workspace-livy-memory/
MEMORY_DIR = BASE_DIR / "memory"
CURATED_DIR = MEMORY_DIR / "curated"
LOGS_DIR = MEMORY_DIR / "logs"
SIGNAL_EVENTS_FILE = MEMORY_DIR / "signal-events.jsonl"
CURATION_LOG_FILE = MEMORY_DIR / "curation-log.md"

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)

import os
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "-5158607302")

from signal_bus import SignalBus
from collectors.tldv_collector import TLDVCollector
from topic_analyzer import TopicAnalyzer
from auto_curator import AutoCurator


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

    log_structured("INFO", correlation_id, "signal_bus", "events_collected",
                    total=len(bus.events))

    # ── 2. Persist signals to JSONL ──────────────────────────────────────
    bus.persist(SIGNAL_EVENTS_FILE)
    log_structured("INFO", correlation_id, "signal_bus", "events_persisted",
                    path=str(SIGNAL_EVENTS_FILE), count=len(bus.events))

    # ── 3. Analyze + Auto-curate per topic ───────────────────────────────
    analyzer = TopicAnalyzer()
    curator = AutoCurator()
    curation_log_lines = []
    applied_count = 0

    # Group signals by topic
    topics = set(e.topic_ref for e in bus.events if e.topic_ref)
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

    # ── 4. Write curation log ───────────────────────────────────────────
    if curation_log_lines:
        with CURATION_LOG_FILE.open("a") as f:
            f.write("\n".join(curation_log_lines) + "\n")

    # ── 5. Send Telegram summary ─────────────────────────────────────────
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
