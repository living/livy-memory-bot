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

    # Stage: LLM enrichment for meetings with transcripts
    try:
        from vault.enrich.llm_summarize import enrich_meeting_file

        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_ANON_KEY")

        enriched = 0
        if supabase_url and supabase_key:
            import requests
            from datetime import datetime, timedelta, timezone
            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
            resp = requests.get(
                f"{supabase_url}/rest/v1/meetings",
                headers={"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}"},
                params={
                    "select": "id,name,created_at,whisper_transcript",
                    "whisper_transcript": "not.is.null",
                    "created_at": f"gte.{cutoff}",
                    "order": "created_at.desc",
                    "limit": "50",
                },
                timeout=30,
            )
            if resp.status_code == 200:
                from vault.ingest.entity_writer import _slugify
                for raw in resp.json():
                    transcript = raw.get("whisper_transcript", "")
                    if not transcript or len(transcript.strip()) < 50:
                        continue
                    title = raw.get("name", "")
                    created = (raw.get("created_at") or "")[:10]
                    if not created:
                        continue
                    slug = _slugify(title)
                    matches = list((vault_root / "entities" / "meetings").glob(f"{created} {slug}.md"))
                    if not matches:
                        matches = list((vault_root / "entities" / "meetings").glob(f"{created}*{slug[:30]}*"))
                    if not matches:
                        continue
                    mf = matches[0]
                    text = mf.read_text(encoding="utf-8")
                    if "<!-- Enriquecimento TLDV" not in text:
                        continue
                    if enrich_meeting_file(mf, transcript):
                        enriched += 1
                        print(f"  [enrich] {mf.name}")
        result["meetings_enriched"] = enriched
    except Exception as exc:
        import traceback
        traceback.print_exc()
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
