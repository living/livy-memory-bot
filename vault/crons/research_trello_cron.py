"""Research poller cron for Trello source.

Scheduled interval: RESEARCH_TRELLO_INTERVAL_MIN (default 20 min) via openclaw cron.

Acquires .research/trello/lock (TTL 600 s) before polling; releases after run.
After each successful run rebuilds .research/trello/state.json from the SSOT
(state/identity-graph/state.json).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Ensure vault package is on path when run as script
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from vault.research.lock_manager import acquire_lock, release_lock, LOCK_TTL
from vault.research.pipeline import ResearchPipeline

LOCK_PATH = ".research/trello/lock"
RESEARCH_DIR = ".research/trello"
STATE_PATH = "state/identity-graph/state.json"


def main() -> None:
    try:
        # Batch cadence: 4x/day (0h, 6h, 12h, 18h BRT) — interval_min is informational only.
        # Actual schedule is governed by OpenClaw cron (id: 49d1d21e-9bad-4e20-a638-196dcf29f37e).
        interval_min = int(os.environ.get("RESEARCH_TRELLO_INTERVAL_MIN", "360"))  # 6h
    except ValueError:
        interval_min = 20
        logger.warning(
            "RESEARCH_TRELLO_INTERVAL_MIN=%r is not a valid integer; falling back to %d",
            os.environ.get("RESEARCH_TRELLO_INTERVAL_MIN"),
            interval_min,
        )
    print(f"[research_trello] acquiring lock {LOCK_PATH} (ttl={LOCK_TTL}s, batch cadence 4x/day BRT)")

    if not acquire_lock(LOCK_PATH):
        print("[research_trello] lock held by another process — skipping this run")
        return

    try:
        pipeline = ResearchPipeline(
            source="trello",
            state_path=STATE_PATH,
            research_dir=RESEARCH_DIR,
            read_only_mode=True,
        )

        result = pipeline.run()
        print(
            f"[research_trello] done — processed={result['events_processed']}, "
            f"skipped={result['events_skipped']}, status={result['status']}"
        )
    finally:
        release_lock(LOCK_PATH)


if __name__ == "__main__":
    main()
