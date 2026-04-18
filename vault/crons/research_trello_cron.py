"""Research poller cron for Trello source.

Scheduled interval: RESEARCH_TRELLO_INTERVAL_MIN (default 20 min) via openclaw cron.

Acquires .research/trello/lock (TTL 600 s) before polling; releases after run.
After each successful run rebuilds .research/trello/state.json from the SSOT
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

LOCK_PATH = ".research/trello/lock"
RESEARCH_DIR = ".research/trello"
STATE_PATH = "state/identity-graph/state.json"


def main() -> None:
    interval_min = int(os.environ.get("RESEARCH_TRELLO_INTERVAL_MIN", "20"))
    print(f"[research_trello] acquiring lock {LOCK_PATH} (ttl={LOCK_TTL}s, interval={interval_min}min)")

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
