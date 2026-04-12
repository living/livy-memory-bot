#!/usr/bin/env bash
# vault-crosslink.sh — Stage 8: Cross-link pipeline
# Runs after vault-ingest to create card/PR relationships
set -euo pipefail

cd "$(dirname "$0")/.."

export GITHUB_PERSONAL_ACCESS_TOKEN="${GITHUB_PERSONAL_ACCESS_TOKEN:-$(grep GITHUB_PERSONAL_ACCESS_TOKEN ~/.openclaw/.env 2>/dev/null | cut -d= -f2-)}"
export TRELLO_API_KEY="${TRELLO_API_KEY:-$(grep TRELLO_API_KEY ~/.openclaw/.env 2>/dev/null | head -1 | cut -d= -f2-)}"
export TRELLO_TOKEN="${TRELLO_TOKEN:-$(grep TRELLO_TOKEN ~/.openclaw/.env 2>/dev/null | head -1 | cut -d= -f2-)}"

VAULT_ROOT="${1:-memory/vault}"

python3 -c "
import os, json
from pathlib import Path
from vault.ingest.crosslink_builder import run_crosslink
from vault.ingest.index_manager import rebuild_index
from vault.ingest.vault_lint_scanner import run_lint_scans

vault = Path('$VAULT_ROOT')
result = run_crosslink(
    vault,
    dry_run=False,
    github_token=os.environ.get('GITHUB_PERSONAL_ACCESS_TOKEN'),
    trello_api_key=os.environ.get('TRELLO_API_KEY'),
    trello_token=os.environ.get('TRELLO_TOKEN'),
)
rebuild_index(vault)

edges = result.get('edges', {})
total = sum(edges.values()) if edges else 0
print(f'Crosslink: {total} edges ({edges})')

report = run_lint_scans(vault)
m = report['metrics']
print(f'Lint: {m[\"total_entities\"]} entities, {m[\"total_relationships\"]} relationships')
"
