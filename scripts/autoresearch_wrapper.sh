#!/bin/bash
# Autoresearch Cron Wrapper — loads env and runs autoresearch_cron.py

set -euo pipefail

WORKSPACE="/home/lincoln/.openclaw/workspace-livy-memory"
cd "$WORKSPACE"

# Load credentials
if [ -f ~/.openclaw/.env ]; then
    set -a
    source ~/.openclaw/.env
    set +a
fi

# Run autoresearch
exec python3 scripts/autoresearch_cron.py 2>&1
