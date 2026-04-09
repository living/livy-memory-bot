#!/usr/bin/env bash
# curation_cron_wrapper.sh — Secure wrapper for curation_cron.py
# Loads credentials from ~/.openclaw/.env instead of inline args

set -euo pipefail

# Load environment from .env
if [[ -f ~/.openclaw/.env ]]; then
    set -a
    source ~/.openclaw/.env
    set +a
else
    echo "ERROR: ~/.openclaw/.env not found" >&2
    exit 1
fi

# Validate required vars
: "${SUPABASE_URL:?Missing SUPABASE_URL}"
: "${SUPABASE_SERVICE_ROLE_KEY:?Missing SUPABASE_SERVICE_ROLE_KEY}"
: "${GITHUB_PERSONAL_ACCESS_TOKEN:?Missing GITHUB_PERSONAL_ACCESS_TOKEN}"
: "${TELEGRAM_TOKEN:?Missing TELEGRAM_TOKEN}"

# Fact-check precondition (non-fatal): missing key degrades to skipped gate in fact_checker
if [[ -z "${CONTEXT7_API_KEY:-}" ]]; then
    echo "WARN: CONTEXT7_API_KEY missing; fact-check gate will run in skipped mode" >&2
fi

# Execute curation script
cd /home/lincoln/.openclaw/workspace-livy-memory
exec python3 skills/memoria-consolidation/curation_cron.py "$@"
