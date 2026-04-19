#!/usr/bin/env bash
set -euo pipefail

# Testa o motor de evolução (research pipeline) em janela semanal sem tocar no estado de produção.
# Uso:
#   scripts/test_week_evolution.sh [YYYY-MM-DD]
# Exemplo:
#   scripts/test_week_evolution.sh 2026-04-19
# Se omitido, usa data UTC atual.

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

REF_DATE="${1:-$(date -u +%F)}"

# Calcula segunda e sexta da semana da data de referência
MONDAY="$(date -u -d "$REF_DATE -$(( $(date -u -d "$REF_DATE" +%u) - 1 )) days" +%F)"
FRIDAY="$(date -u -d "$MONDAY +4 days" +%F)"
CUTOFF="$(date -u -d "$MONDAY -1 day" +%FT00:00:00+00:00)"

STAMP="$(date -u +%Y%m%d%H%M%S)"
TMP_STATE="tmp/state-week-test-${STAMP}.json"
TMP_BASE="tmp/research-week-${STAMP}"
OUT_SUMMARY="${TMP_BASE}/summary.txt"

mkdir -p "$TMP_BASE/tldv" "$TMP_BASE/github" "$TMP_BASE/trello"

echo "[week-test] referência: $REF_DATE"
echo "[week-test] janela: $MONDAY .. $FRIDAY"
echo "[week-test] cutoff: $CUTOFF"

# Clona estado canônico para estado temporário
python3 << PYEOF
import json
from pathlib import Path
import os

src = Path("$ROOT_DIR/state/identity-graph/state.json")
dst = Path("$TMP_STATE")
cutoff = "$CUTOFF"
state = json.loads(src.read_text())
state.setdefault('last_seen_at', {})['tldv'] = cutoff
state.setdefault('last_seen_at', {})['github'] = cutoff

dst.parent.mkdir(parents=True, exist_ok=True)
dst.write_text(json.dumps(state, ensure_ascii=False, indent=2))
print(f"[week-test] tmp_state: {dst}")
PYEOF

# Roda pipelines em read_only_mode=true usando o estado temporário
python3 << PYEOF
import json, sys, os
from pathlib import Path
sys.path.insert(0, ".")
from vault.research.pipeline import ResearchPipeline

state_path = "$TMP_STATE"
base = Path("$TMP_BASE")
summary_path = Path("$OUT_SUMMARY")

sources = [('tldv', base / 'tldv'), ('github', base / 'github'), ('trello', base / 'trello')]
results = {}

for source, rdir in sources:
    p = ResearchPipeline(
        source=source,
        state_path=state_path,
        research_dir=rdir,
        read_only_mode=True,
    )
    res = p.run()
    results[source] = res
    print(f"[week-test] {source}: processed={res['events_processed']} skipped={res['events_skipped']} status={res['status']}")

# Conta event_processed no audit
lines = ["# Week Evolution Test Summary", ""]
for source, rdir in sources:
    audit = rdir / 'audit.log'
    processed = 0
    if audit.exists():
        try:
            rows = json.loads(audit.read_text())
            processed = sum(1 for row in rows if row.get('action') == 'event_processed')
        except Exception:
            processed = -1
    lines.append(f"- {source}: events_processed={results[source]['events_processed']} audit_event_processed={processed}")

# Estado final (cursores)
state = json.loads(Path(state_path).read_text())
last_seen = state.get('last_seen_at', {})
lines.append('')
lines.append('## last_seen_at (tmp state)')
for src in ('tldv','github','trello'):
    lines.append(f"- {src}: {last_seen.get(src)}")

summary_path.write_text('\n'.join(lines))
print(f"[week-test] summary: {summary_path}")
PYEOF

echo
echo "===== RESUMO ====="
cat "$OUT_SUMMARY"
echo "==================="

echo
echo "[week-test] artefatos em: $TMP_BASE"
echo "[week-test] estado temporário: $TMP_STATE"
