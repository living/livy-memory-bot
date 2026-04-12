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
    # Stage: Auto-fix orphan links
    try:
        from vault.lint.auto_fix import auto_fix_orphan_links
        fix_result = auto_fix_orphan_links(vault_root)
        result["auto_fix"] = fix_result
    except Exception as exc:
        print(f"[WARN] Auto-fix failed: {exc}", file=sys.stderr)

    # Stage: LLM enrichment for meetings with empty summaries
    try:
        from vault.enrich.llm_summarize import enrich_meeting_file

        meetings_dir = vault_root / "entities" / "meetings"
        enriched = 0
        if meetings_dir.exists():
            for mf in meetings_dir.glob("*.md"):
                text = mf.read_text(encoding="utf-8")
                # Only enrich meetings that have the placeholder comment
                if "<!-- Enriquecimento TLDV: tópicos e pontos-chave -->" not in text:
                    continue
                # For now, skip LLM enrichment if no transcript available
                # (transcripts come from Supabase, not stored in the md file)
                # This stage will be enhanced later when transcript storage is added
                pass
        result["meetings_enriched"] = enriched
    except Exception as exc:
        print(f"[WARN] LLM enrichment failed: {exc}", file=sys.stderr)

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
