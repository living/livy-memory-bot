#!/usr/bin/env python3
"""Vault crosslink pipeline cron — Stage 8."""
import os
import sys
from pathlib import Path

# Add workspace to path (same pattern as vault_ingest_cron.py)
workspace = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(workspace))

from vault.ingest.crosslink_builder import run_crosslink
from vault.ingest.index_manager import rebuild_index


def main():
    vault_path = workspace / "memory" / "vault"
    github_token = os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN")
    trello_api_key = os.environ.get("TRELLO_API_KEY")
    trello_token = os.environ.get("TRELLO_TOKEN")

    result = run_crosslink(
        vault_path,
        dry_run=False,
        github_token=github_token,
        trello_api_key=trello_api_key,
        trello_token=trello_token,
    )
    rebuild_index(vault_path)
    print(f"Crosslink done: {result}")


if __name__ == "__main__":
    main()
