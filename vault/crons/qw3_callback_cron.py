#!/usr/bin/env python3
"""
QW-3 Callback Cron — processes approve/reject for QW-2 pending decisions.
Triggered by Telegram callback_query events or by DM poller.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

_WS = Path(__file__).resolve().parents[2]


def load_env():
    env_file = Path.home() / ".openclaw" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def handle_approve() -> dict:
    """Process approve — write pending decisions, consolidate, update MEMORY."""
    sys.path.insert(0, str(_WS))

    from vault.qw2.callback_handler import confirm_pending
    from vault.qw2.consolidate import consolidate_topic
    from vault.qw2.update_memory_index import update_memory_index

    result = confirm_pending()
    if result.get("written", 0) > 0:
        topics = [
            "delphos-video-vistoria.md",
            "infra.md",
            "bat-conectabot-observability.md",
            "livy-memory-agent.md",
            "general.md",
        ]
        for t in topics:
            p = _WS / "memory" / "vault" / "decisions" / t
            if p.exists():
                try:
                    consolidate_topic(p, dry_run=False)
                except Exception as e:
                    print(f"[qw3-callback] consolidate error {t}: {e}")
        try:
            update_memory_index()
        except Exception as e:
            print(f"[qw3-callback] MEMORY update error: {e}")
    return result


def handle_reject() -> dict:
    """Process reject — archive pending decisions."""
    sys.path.insert(0, str(_WS))
    from vault.qw2.callback_handler import cancel_pending
    return cancel_pending()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="QW-3 Callback Handler")
    parser.add_argument("--action", choices=["approve", "reject"], required=True)
    args = parser.parse_args()

    load_env()
    sys.path.insert(0, str(_WS))

    if args.action == "approve":
        result = handle_approve()
        print(f"[qw3-callback] Approved: {result}")
    else:
        result = handle_reject()
        print(f"[qw3-callback] Rejected: {result}")


if __name__ == "__main__":
    main()
