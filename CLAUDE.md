# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

This is the **Livy Memory Agent** workspace — an agentic memory system for Living Consultoria. It maintains a 3-layer memory architecture for institutional context:

| Layer | Source | Format |
|-------|--------|--------|
| Observations | `~/.claude-mem/claude-mem.db` | SQLite |
| Curated | `MEMORY.md` + `memory/curated/*.md` | Markdown |
| Operational | `HEARTBEAT.md` + `memory/consolidation-log.md` | Markdown |

## Feedback Learning

`learn_from_feedback.py` runs at START of autoresearch_cron.py, reads `memory/feedback-log.jsonl`, generates `memory/learned-rules.md`. No separate cron needed — feedback accumulates between autoresearch runs.

## Memory Consolidation

Run the 4-phase consolidation script:

```bash
python3 skills/memoria-consolidation/consolidate.py
```

Phases: Orientation → Gather Signal → Consolidation → Prune & Index
Log output: `memory/consolidation-log.md`
**Mente Coletiva:** consolidation processes BOTH workspaces: memory-agent + Livy Deep (main). Both MEMORY.md indexes are validated (<200 lines).

## File Structure

```
.claude/                   # Workspace config (napkin, plans, specs)
├── napkin.md
├── plans/                 # Implementation plans
├── specs/                 # Design documents
└── worktrees/             # Isolated git worktrees

memory/                     # Curated long-term memory
├── curated/               # Topic files by project/agent
│   └── *.md
├── .archive/              # Stale files (>60 days, moved here)
│   └── inbox/             # Raw inputs (audio, HTML, etc.)
├── consolidation-log.md   # Last consolidation output
└── signal-events.jsonl     # Cross-curation signal events

root:                       # Operational files (canonical)
├── SOUL.md                 # Agent persona
├── IDENTITY.md             # Agent identity
├── AGENTS.md               # Agent operational config
├── MEMORY.md               # Curated memory index
├── HEARTBEAT.md            # Operational dashboard
├── TOOLS.md                # Tool references
├── USER.md                 # User context
└── CLAUDE.md               # This file
```

## Topic Files

Topic files in `memory/curated/` contain detailed project/agent context. They are referenced from `MEMORY.md`. Keep `MEMORY.md` under 200 lines — push details to topic files.

## Operational Rules

- Read `.claude/SOUL.md` and `.claude/IDENTITY.md` at session start
- Read `MEMORY.md` as the curated memory index
- When encountering technical decisions: update the relevant topic file
- When encountering stale entries: register for consolidation
- `HEARTBEAT.md` is the operational dashboard — keep it current

## Skills

**Skill central de contexto histórico:** `memory-assistant` (em `~/.openclaw/workspace/skills/memory-assistant/`) — consulta built-in memory search E claude-mem 3-layer automaticamente quando o agente precisa de contexto de sessões passadas.

**Skills do OpenClaw** vivem em `~/.openclaw/workspace/skills/` — compartilhadas por todos os agentes. Todas precisam de YAML frontmatter com `name` + `description`.

## Skill Development — Regras Importantes

### Skills precisam YAML frontmatter
OpenClaw só reconhece skills com `name` e `description` em YAML frontmatter:
```yaml
---
name: minha-skill
description: Descrição pushy. USE ESTA SKILL SEMPRE que...
---
```
Sem frontmatter, `openclaw skills list` não mostra a skill.

### Testar skills localmente
```bash
source ~/.openclaw/.env && export SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY && python3 skills/minha-skill/search.py --query "teste"
```
Python subprocessos não herdam env vars automaticamente — precisa de `source` + `export`.

### Tabela TLDV correta
- **ERRADO**: `meeting_memories` (vector store secundário, só resumos curtos)
- **CERTO**: `meetings` + `summaries` (projeto `fbnelbwsjfjnkiexxtom`, dados ricos)
- `meeting_participants` frequentemente vazio — não filtrar por ele
- `enrichment_context` (PRs/Cards) é genérico (últimos 7 dias), não específico da reunião

## OpenClaw Automation

**Cron jobs:** `openclaw cron list` / `openclaw cron add` / `openclaw cron run <id>` / `openclaw cron edit <id>`
**Cron timeout flag:** `--timeout-seconds` (not `--timeout`)
**Cron run:** `openclaw cron run <id>` (no --force flag — it runs immediately)
**Cron DM delivery:** `--announce --to tg:7426291192` for user DM

**Bot:** `@livy_agentic_memory_bot` (feedback) — DM to report actions with 👍/👎 buttons
**Autoresearch cron ID:** `0c388629-3465-4825-a791-16c46c9d1300` (every 1h, memory-agent)
**Feedback cron:** memory-agent-feedback-learn (cron ID aa5cd560, at :45) — processes accumulated feedback before each autoresearch run

## Infrastructure

**Telegram bot tokens:** OpenClaw gateway (`8738927361:AAE2COOt...`) conflicts with manual getUpdates — use separate bot `8725269523:AAFqAFEF...` for polling only
**Telegram polling:** Use `getUpdates` polling only — webhook conflicts with getUpdates (409 Conflict) and is blocked by DNS issues on this server
**Caddyfile:** `/home/lincoln/.local/etc/caddy/Caddyfile` — `/memory-callback/` active; `/telegram-feedback/` route removed (was unused)
**Test feedback:** Send test message via API, click button, verify with `tail memory/feedback-log.jsonl`
**Telegram getUpdates:** Calling via curl consumes pending updates from Telegram — use for testing only, not in production polling code
**Systemd user services:** `~/.config/systemd/user/<name>.service` — control with `systemctl --user <start|stop|status>`
**Feedback poller:** Managed by `feedback-webhook.service` (systemd). Use `systemctl --user restart feedback-webhook.service` — do NOT run manually (creates duplicate processes causing 409 Conflict)
**Feedback context:** `learned-rules.md` + `openclaw memory search` enrich each file summary before sending — negative rules shown as warnings in summary message
**Consolidation output:** "DRY RUN" + "mudanças pendentes" messages are informational only — changes ARE applied if pending count > 0
**Autoresearch script:** `python3 scripts/autoresearch_cron.py` — sends files via Telegram Direct API with feedback buttons, processes feedback at start
**Dream:** `python3 skills/memoria-consolidation/dream_all.py` — processes sessions from main (Livy Deep) and both memory workspaces
**Audio Processing:** NEVER use the local `whisper` binary (`~/.local/bin/whisper`) — it crashes the VPS due to high resource usage. Always use the OpenAI API with `OPENAI_WHISPER_KEY` from `~/.openclaw/.env`.

## Signal Cross-Curation

Sistema de curadoria inteligente que cruza sinais de TLDV + GitHub + Logs + Feedback para manter topic files atualizados.
**Script:** `skills/memoria-consolidation/curation_cron.py`
**Cron:** `53b45f6f-cb68-4b79-8610-0b4f4db6e585` (every 4h, memory-agent)

**Fontes:** TLDV (priority 1) → Logs (2) → GitHub (3) → Feedback (4)
**Output files:** `memory/signal-events.jsonl`, `memory/curation-log.md`, `memory/conflict-queue.md`
**Topic files atualizados:** `memory/curated/*.md`

**Rodar manualmente:**
```bash
cd /home/lincoln/.openclaw/workspace-livy-memory && source ~/.openclaw/.env && export SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY GITHUB_PERSONAL_ACCESS_TOKEN && python3 skills/memoria-consolidation/curation_cron.py
```

## TLDV summaries schema (confirmado)

`decisions[]`, `topics[]` existem; `action_items`, `status_changes`, `consensus_topics` NÃO existem (error 42703).

## GitHub token env var

`GITHUB_PERSONAL_ACCESS_TOKEN` (not `GITHUB_TOKEN`)

## Parent path em scripts em skills/

`Path(__file__).resolve().parents[1]` aponta para `skills/`, não workspace root. Para alcançar `workspace/memory/`, use `parents[2]`.

## Cron jobs para scripts Python

Editar `~/.openclaw/cron/jobs.json` diretamente — `openclaw cron add` é baseado em agente (envia mensagem para agente, não executa script direto).

## Subagent-driven development

Para implementar planos com múltiplas tarefas, usar `EnterWorktree` + agente por tarefa + review em duas fases (spec compliance + code quality).

### Running tests in skills/memoria-consolidation

Unit tests: `cd <worktree-root> && python3 -m pytest skills/memoria-consolidation/test_reconciliation.py -q`
Functional scripts: `cd <worktree-root> && python3 scripts/test_reconciliation.py`
Security tests: `cd <worktree-root> && python3 scripts/test_security.py`

Hyphenated module names (e.g. `memoria-consolidation`) cannot be used in Python import paths.
Scripts in `scripts/` must use `sys.path.insert(0, ...)` to import from the skills directory.

## Reconciliation Pipeline (Shadow/Write Mode)

The reconciliation pipeline lives in `skills/memoria-consolidation/` and reconciles
topic files against concrete evidence sources (TLDV, GitHub, logs, feedback).

**Files:** evidence_normalizer.py → fact_snapshot_builder.py → reconciler.py →
decision_ledger.py → topic_rewriter.py
**Script:** `skills/memoria-consolidation/curation_cron.py`
**Outputs:** `memory/reconciliation-ledger.jsonl`, `memory/reconciliation-report.md`

**Shadow mode (default):** runs reconciliation end-to-end but does not modify topic files.
**Write mode:** guarded by `RECONCILIATION_WRITE_MODE=1` — archives to `memory/.archive/YYYYMMDDHHMM/`
then uses atomic `.tmp → replace` pattern. Only `tldv-pipeline-state.md` is in scope for the pilot.


### Decision ledger is append-only (audit log)

`DecisionLedger` writes to `memory/reconciliation-ledger.jsonl` — this is an append-only audit trail.
`deduplicate_records()` removes within-run duplicates; `append_many()` also checks existing ledger keys
to prevent cross-run duplicates (entity_key + rule_id). Downstream consumers needing "current state"
should query the most recent entry per entity.

### Known pre-existing test failure

`test_embedding_cache_has_ttl` in `scripts/test_security.py` fails with
`AttributeError: module 'search' has no attribute 'EMBEDDING_CACHE'` — this is a pre-existing
bug in the meetings-tldv skill. Ignore it when running test_security.py.

## meetings-tldv Skill

- **Skill:** `skills/meetings-tldv/` — queries Supabase TLDV (meeting_memories table)
- **Feedback:** `memory/meetings-tldv-feedback-log.jsonl` (isolated per skill)
- **Learned rules:** `memory/meetings-tldv-learned-rules.md`
- **Autoresearch:** `scripts/meetings_tldv_autoresearch.py` (daily, invoked by autoresearch_cron.py)
- **PREREQUISITE:** Supabase RPC `match_summary_vectors` must exist — fallback to ILIKE if not
- **Supabase schema:** Always verify actual columns first — GET /rest/v1/table_name?select=*&limit=3 — never trust schema docs
- **Filter syntax:** Supabase REST API uses dot notation — `field.ilike.*{value}*`, `field.eq.{value}`, not Python client syntax
- **New skill with feedback:** add prefix to callback_data, add routing case in feedback_poller.py, add ALLOWED_USER_IDS check, add log file path to FEEDBACK_FILES
- **Token security:** os.getenv() with fail-fast — never hardcode tokens or secrets
- **Time-bounded cache:** use dict with (value, timestamp) — lru_cache has no TTL enforcement
- **Test suites:** skills/X/test_X.py (unit) + scripts/test_X.py (functional) + scripts/test_security.py (security) — run all three after changes
