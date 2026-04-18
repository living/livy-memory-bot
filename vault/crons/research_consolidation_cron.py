"""Daily consolidation cron — replaces dream-memory-consolidation.

Scheduled: daily at 07h BRT via openclaw cron.
Replaces the legacy `dream-memory-consolidation` job.

Responsibilities:
1. Load .env into os.environ  (same pattern as vault_ingest_cron)
2. Run TLDV and GitHub pipelines to flush any pending events
3. Compact processed keys (180-day retention)
4. Monthly snapshot (days 1–5 of each month)
5. Append summary to memory/consolidation-log.md
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure vault package is on path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vault.research.lock_manager import acquire_lock, release_lock, LOCK_TTL
from vault.research.pipeline import ResearchPipeline
from vault.research.state_store import (
    compact_processed_keys,
    load_state,
    monthly_snapshot,
    state_metrics,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LOCK_PATH = ".research/consolidation/lock"
RESEARCH_DIR_TLDV = ".research/tldv"
RESEARCH_DIR_GITHUB = ".research/github"
STATE_PATH = "state/identity-graph/state.json"
CONSOLIDATION_LOG = "memory/consolidation-log.md"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_env() -> None:
    """Load .env file into os.environ (same pattern as vault_ingest_cron)."""
    env_file = Path.home() / ".openclaw" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _utc_now() -> datetime:
    """Clock indirection for testability."""
    return datetime.now(timezone.utc)


def _append_consolidation_log(entry: dict) -> None:
    """Append a consolidation entry to memory/consolidation-log.md."""
    log_path = Path(CONSOLIDATION_LOG)
    ts = _utc_now().isoformat()
    entry_md = (
        f"\n\n## Consolidation {ts}\n"
        + json.dumps(entry, indent=2, ensure_ascii=False)
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry_md)


def _is_first_five_days() -> bool:
    """Return True when today is day 1-5 of the month (UTC)."""
    return 1 <= _utc_now().day <= 5


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    load_env()
    print(
        f"[research_consolidation] starting daily consolidation "
        f"(replaces dream-memory-consolidation)"
    )

    # Acquire consolidation lock (shared TTL semantics with per-source crons)
    if not acquire_lock(LOCK_PATH):
        print("[research_consolidation] lock held — skipping")
        print(json.dumps({"skipped_reason": "locked", "run_at": _utc_now().isoformat()}))
        return

    try:
        # 1) Run TLDV pipeline
        print("[research_consolidation] running TLDV pipeline flush...")
        tldv_pipeline = ResearchPipeline(
            source="tldv",
            state_path=STATE_PATH,
            research_dir=RESEARCH_DIR_TLDV,
            read_only_mode=True,
        )
        tldv_result = tldv_pipeline.run()
        print(f"[research_consolidation] TLDV: {tldv_result}")

        # 2) Run GitHub pipeline
        print("[research_consolidation] running GitHub pipeline flush...")
        gh_pipeline = ResearchPipeline(
            source="github",
            state_path=STATE_PATH,
            research_dir=RESEARCH_DIR_GITHUB,
            read_only_mode=True,
        )
        gh_result = gh_pipeline.run()
        print(f"[research_consolidation] GitHub: {gh_result}")

        # 3) Compact processed keys (180-day retention)
        print("[research_consolidation] compacting processed keys (180-day retention)...")
        compact_processed_keys(retention_days=180, state_path=STATE_PATH)

        # 4) Monthly snapshot (days 1–5 of month)
        snapshot_result = None
        if _is_first_five_days():
            print("[research_consolidation] creating monthly snapshot...")
            snapshot_result = monthly_snapshot(state_path=STATE_PATH)
            print(f"[research_consolidation] snapshot: {snapshot_result}")

        # 5) Metrics
        metrics = state_metrics(state_path=STATE_PATH)
        print(f"[research_consolidation] state metrics: {metrics}")

        # 6) Log entry
        run_at = _utc_now().isoformat()
        log_entry = {
            "run_at": run_at,
            "tldv": {
                "events_processed": tldv_result.get("events_processed", 0),
                "events_skipped": tldv_result.get("events_skipped", 0),
                "status": tldv_result.get("status"),
            },
            "github": {
                "events_processed": gh_result.get("events_processed", 0),
                "events_skipped": gh_result.get("events_skipped", 0),
                "status": gh_result.get("status"),
            },
            "metrics": metrics,
            "snapshot_created": snapshot_result is not None,
        }
        _append_consolidation_log(log_entry)
        print(f"[research_consolidation] log entry appended to {CONSOLIDATION_LOG}")

        result = {
            "status": "success",
            "run_at": run_at,
            "tldv": log_entry["tldv"],
            "github": log_entry["github"],
            "metrics": metrics,
            "snapshot_created": log_entry["snapshot_created"],
        }
        print(json.dumps(result, default=str))
    finally:
        release_lock(LOCK_PATH)


if __name__ == "__main__":
    main()
