"""Cron entry point for vault-ingest."""
import json
import os
import sys
from pathlib import Path


def load_env():
    """Load .env file into os.environ."""
    env_file = Path.home() / ".openclaw" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main():
    load_env()
    # Add workspace to path
    workspace = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(workspace))

    from vault.ingest.run_context import new_run_context
    from vault.ingest.cursor import acquire_lock, release_lock
    from vault.ingest.external_ingest import run_external_ingest

    vault_root = workspace / "memory" / "vault"
    tldv_token = os.environ.get("TLDV_JWT_TOKEN")
    dry_run = os.environ.get("VAULT_DRY_RUN", "").lower() in ("1", "true", "yes")

    result = run_external_ingest(
        vault_root=vault_root,
        tldv_token=tldv_token,
        meeting_days=1,
        dry_run=dry_run,
    )

    # Output structured JSON for cron logging
    print(json.dumps(result, default=str, indent=2))

    # Exit code based on errors
    if result.get("skipped_reason"):
        print(f"SKIP: {result['skipped_reason']}", file=sys.stderr)
        sys.exit(0)
    if result.get("errors"):
        print(f"ERRORS: {len(result['errors'])}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
