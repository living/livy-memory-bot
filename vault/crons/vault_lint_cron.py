"""Cron entry point for vault-lint."""
import json
import os
import sys
from pathlib import Path


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


def main():
    load_env()
    workspace = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(workspace))

    from vault.ingest.run_context import new_run_context
    from vault.ingest.cursor import acquire_lock, release_lock
    from vault.ingest.log_manager import append_log
    from vault.ingest.vault_lint_scanner import run_lint_scans

    vault_root = workspace / "memory" / "vault"
    ctx = new_run_context(vault_root=vault_root)

    if not acquire_lock(vault_root, "vault-lint"):
        print(json.dumps({"skipped_reason": "locked", "run_id": ctx.run_id}))
        sys.exit(0)

    try:
        result = run_lint_scans(vault_root)
        result["run_id"] = ctx.run_id

        # Log
        append_log(
            vault_root,
            "vault-lint",
            {
                "orphans": len(result.get("orphans", [])),
                "stale": len(result.get("stale", [])),
                "gaps": len(result.get("gaps", [])),
                "contradictions": len(result.get("contradictions", [])),
            },
            run_id=ctx.run_id,
        )

        print(json.dumps(result, default=str, indent=2))
    finally:
        release_lock(vault_root)


if __name__ == "__main__":
    main()
