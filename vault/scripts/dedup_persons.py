"""One-shot script to deduplicate existing person files in the vault.

Uses identity_map.yaml via crosslink_dedup.dedup_with_identity_map().
Run: python3 -m vault.scripts.dedup_persons
"""
from __future__ import annotations

import sys
from pathlib import Path


def main():
    workspace = Path(__file__).resolve().parents[2]
    vault_root = workspace / "memory" / "vault"

    # Ensure workspace is on path
    sys.path.insert(0, str(workspace))

    from vault.ingest.crosslink_dedup import dedup_with_identity_map
    merged = dedup_with_identity_map(vault_root)
    print(f"Done. {merged} duplicates merged.")


if __name__ == "__main__":
    main()
