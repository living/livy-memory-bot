"""Research poller cron for TLDV source.

Scheduled interval: RESEARCH_TLDV_INTERVAL_MIN (default 15 min) via openclaw cron.

Acquires .research/tldv/lock (TTL 600 s) before polling; releases after run.
After each successful run rebuilds .research/tldv/state.json from the SSOT
(state/identity-graph/state.json).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure vault package is on path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vault.research.lock_manager import acquire_lock, release_lock, LOCK_TTL
from vault.research.pipeline import ResearchPipeline

LOCK_PATH = ".research/tldv/lock"
RESEARCH_DIR = ".research/tldv"
STATE_PATH = "state/identity-graph/state.json"


def main() -> None:
    # Batch cadence: 4x/day (0h, 6h, 12h, 18h BRT) — interval_min is informational only.
    # Actual schedule is governed by OpenClaw cron (id: 88e37467-f7dd-4637-a63a-58b6ca4ecef5).
    interval_min = int(os.environ.get("RESEARCH_TLDV_INTERVAL_MIN", "360"))  # 6h
    print(f"[research_tldv] acquiring lock {LOCK_PATH} (ttl={LOCK_TTL}s, batch cadence 4x/day BRT)")

    if not acquire_lock(LOCK_PATH):
        print("[research_tldv] lock held by another process — skipping this run")
        return

    try:
        pipeline = ResearchPipeline(
            source="tldv",
            state_path=STATE_PATH,
            research_dir=RESEARCH_DIR,
            read_only_mode=True,
        )

        result = pipeline.run()
        print(
            f"[research_tldv] done — processed={result['events_processed']}, "
            f"skipped={result['events_skipped']}, status={result['status']}"
        )
    finally:
        release_lock(LOCK_PATH)


if __name__ == "__main__":
    main()
