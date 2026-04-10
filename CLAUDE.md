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

## Credential Security in Cron Jobs

**CRITICAL (2026-04-08):** All credentials were found hardcoded inline in `~/.openclaw/cron/jobs.json`. This exposes secrets in process logs and command history.

**Solution:** Wrapper scripts that load credentials from `~/.openclaw/.env`.

**Created wrappers:**
- `skills/memoria-consolidation/curation_cron_wrapper.sh`
- `workspace/operacional/bat/jobs/intraday_wrapper.sh`
- `workspace/operacional/bat/jobs/daily_wrapper.sh`
- `workspace/operacional/delphos/jobs/midday_wrapper.sh`
- `workspace/operacional/delphos/jobs/daily_wrapper.sh`

**Pattern:**
```bash
set -a; source ~/.openclaw/.env; set +a
: "${VAR:?Missing VAR}"  # fail-fast validation
```

**.env vars added:** `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`, `AZURE_APP_ID`, `AZURE_API_KEY`, `SENDGRID_API_KEY`, `MONGO_URI`, `MONGO_DB`

**Cron job IDs with wrappers:** `signal-curation` (53b45f6f), `bat-intraday`, `bat-daily`, `delphos-midday`, `delphos-daily`

**DO NOT:** pass credentials as `VAR=value` inline in cron `payload.message`. Use wrapper scripts.

## Signal Cross-Curation

Sistema de curadoria inteligente que cruza sinais de TLDV + GitHub + Logs + Feedback para manter topic files atualizados.
**Script:** `skills/memoria-consolidation/curation_cron.py`
**Cron:** `53b45f6f-cb68-4b79-8610-0b4f4db6e585` (every 2h, memory-agent)

**Fontes:** TLDV (priority 1) → Logs (2) → GitHub (3) → Feedback (4)
**Output files:** `memory/signal-events.jsonl`, `memory/curation-log.md`, `memory/conflict-queue.md`
**Topic files atualizados:** `memory/curated/*.md`

**Rodar manualmente (secure):**
```bash
cd /home/lincoln/.openclaw/workspace-livy-memory && bash skills/memoria-consolidation/curation_cron_wrapper.sh
```

## Shadow Reconciliation Evolution (2026-04-09)

### Current observed state
- `reconciliation-report.md` shows mode `shadow` on `tldv-pipeline-state.md`
- Latest runs: 10 decisions identified, 10 deferred, 0 confirmed
- `causal_completeness` currently stabilized around `0.60`
- Rule firing: `R005_new_issue_flagged_for_triage` for PR-linked decisions

### Confirmed evidence sources
- `memory/reconciliation-ledger.jsonl` (append-only per decision)
- `memory/reconciliation-report.md` (cycle summary)
- `openclaw cron runs --id 53b45f6f-cb68-4b79-8610-0b4f4db6e585`

### Approved direction (Lincoln)
Priorities: **quality > noise reduction > feedback learning > promotion rate**
- Human intervention: **semi-automatic**
- False positive tolerance: **0 FP/week**
- Triage: **Mattermost + LLM pre-filter**, with Telegram summary + override
- Fact-checking required in decision gate: **Context7 + official docs**

### Design + plan artifacts
- Spec: `.claude/specs/2026-04-09-shadow-evolution-pipeline-design.md`
- Plan: `.claude/plans/2026-04-09-shadow-evolution-pipeline-implementation-plan.md`

### Safety policy for promotion
Auto-promotion allowed only if all are true:
1. `causal_completeness >= 0.85`
2. `>= 2` cross-source evidences
3. `Tier A` (low risk)
4. No active conflict
5. No historical divergence alert

Else → triage (never promote).

### Implementation status (2026-04-10)
Shadow Evolution Pipeline V2 (Tasks 1-10) completed and merged to `master`.

Key operational outcomes:
- Full regression green: `pytest tests/ -q` → **182 passed**
- Live shadow run verified: 59 signals, 10 decisions, 0 promoted, 0 applied
- Append-only artifacts preserved (`signal-events.jsonl`, `reconciliation-ledger.jsonl`, `triage-decisions.jsonl`, `promotion-events.jsonl`)

### Context7 endpoint fix (root-cause)
If fact-check logs show `Context7 lookup failed: [Errno -2] Name or service not known`:
- Cause on this host: `api.context7.com` returns DNS NXDOMAIN
- Correct base URL: `https://context7.com/v1` (not `https://api.context7.com/v1`)
- `fact_checker.py` default base URL already fixed accordingly.

### Subagent runtime caveat
For `sessions_spawn` with `runtime="subagent"`, do **not** pass ACP-only fields.
Unsupported for subagent runtime:
- `streamTo`
- `attachments`
- `attachAs`

**Learning (2026-04-10):** alguns templates de dispatch herdados de ACP podem manter esses campos por engano.
Quando isso acontece, o spawn falha com: `streamTo is only supported for runtime=acp`.
Sempre montar payload mínimo para subagent (`task`, `label`, `runtime`, `agentId`, `cwd`, `mode`, `timeout`).

### Pytest collection conflict note
Collection conflict resolved by renaming:
- `scripts/test_reconciliation.py` → `scripts/test_reconciliation_scripts.py`

This avoids duplicate module-name collision with:
- `skills/memoria-consolidation/test_reconciliation.py`

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

## Session Decisions — 2026-04-10 (Domain Modeling Living)

Resumo consolidado da sessão de design/planejamento:
- Modelagem **domain-first** obrigatória: `Person`, `Project`, `Repo`, `Meeting`, `Card`, `Decision`.
- Relações canônicas com papéis: `author`, `reviewer`, `commenter`, `participant`, `assignee`, `decision_maker`.
- Fontes independentes (GitHub/TLDV/Trello) devem convergir para o **mesmo contrato de domínio**.
- Janela padrão de análise: **30 dias**; consultas estendidas: **90/180/355**.
- Em PRs usar sempre datas `created_at` e `merged_at`.
- Ingestão GitHub com escopo restrito por allowlist:
  - `github.org_allowlist` (required)
  - `github.repo_allowlist` (optional, priority)
  - `github.repo_denylist` (optional)
- Nunca ingerir todos os repositórios visíveis ao token.
- Fluxos separados por cron (per-source), sem orquestrador único:
  - `ingest-github` (hourly)
  - `ingest-tldv` (cadência existente)
  - `ingest-trello` (hourly/change-driven)
- `Decision.project_ref` permanece opcional (intencional) para decisões cross-cutting.
- `window_days` em arestas é **query-origin hint**, não constraint do grafo.
- Dados fora da janela ativa não são deletados por ingestão; marcar `outside_active_window: true` e tratar via política de arquivo/consolidação.
- Prioridades de engenharia: **TDD, resiliência, observabilidade, rastreabilidade**.
- Artefatos oficiais da sessão:
  - Spec: `docs/superpowers/specs/2026-04-10-domain-modeling-livy-design.md`
  - Plan: `docs/superpowers/plans/2026-04-10-domain-modeling-livy-implementation.md`
  - Session notes: `docs/superpowers/session-notes/2026-04-10-domain-modeling-session-summary.md`

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

### test_security.py compatibility

When copying tests between worktrees, verify the API signatures match the target worktree's code:
- `EMBEDDING_CACHE` exists only in `signal-cross-curation`, not in `memory-reconciliation`
- `format_result(meetings, summaries, mode, query)` vs old `(rows, mode, query, similarity)`
- `infer_mode(question, meeting_id)` vs old `(question)` — always pass both args
- `get_headers()` not `get_supabase_headers()`
- default `infer_mode` mode is `"keyword"`, not `"semantic"`

## Memory Vault — Karpathy-style Autonomous Wiki

> **Design doc:** `docs/superpowers/specs/2026-04-10-memory-vault-design.md`
> **Status:** approved 2026-04-10 by Lincoln Quinan Junior

### Arquitetura
- **Vault paralelo:** `memory/vault/` (Obsidian-native, 100% autônomo)
- **Não quebra fluxo atual:** `memory/curated/` permanece intacto na Fase 1
- **Fronteira:** raw imutável = TLDV/Signal/GitHub/Trello; internals podem ser retrabalhados

### Estrutura do vault
```
memory/vault/
├── index.md                    # catálogo navegável (auto-atualizado)
├── log.md                      # timeline append-only
├── AGENTS.md                   # schema de manutenção do vault
├── entities/                   # páginas de entidade (projetos, pessoas, sistemas)
├── decisions/                  # decisões com contexto, impacto, status
├── concepts/                   # conceitos recorrentes
├── evidence/                   # fact-check com fonte oficial
├── lint-reports/               # saídas de lint cycles
└── .cache/fact-check/          # TTL cache Context7 (24h)
```

### Confiança e Evidência
| Score | Condição |
|---|---|
| 🟢 high | 2+ fontes oficiais independentes ou 1 oficial + 1 corroborada |
| 🟡 medium | 1 fonte oficial OU 2+ sinais indiretos |
| 🔴 low | 1 sinal indireto ou inferência |
| ⚫ unverified | sem evidência (não写入 vault) |

### Context7 Policy (prioridade de verificação)
1. `openclaw config.get` / `exec` (estado real)
2. API calls diretas (Supabase, GitHub, TLDV)
3. Docs oficiais em `~/.openclaw/docs/`
4. Fixtures/exports locais

### Obsidian Client (privado, via git worktree)
- `memory/vault/` = git worktree branch `vault/` do repo `living/livy-memory-bot`
- **Plugins recomendados:**
  | Plugin | Uso |
  |---|---|
  | **Obsidian Git** | auto-commit após mudanças do agente |
  | **Dataview** | queries dinâmicas sobre frontmatter |
  | **Graph View** | visualizar rede de entidades e links |
  | **Templater** | template de frontmatter consistente |
  | **QuickAdd** | criar páginas de decisão com estrutura padronizada |
  | **Metaedit** | editar frontmatter sem raw markdown |
  | **Admonition** | callouts tipadas (⚠️ aviso, ✅ resolved, 🔴 critical) |
  | **Heatmap Calendar** | visualizar frequência de updates por página |
  | **Outliner** | organização hierárquica de páginas de decisão |
  | **Icon Shortcodes** | emojis consistentes como prefixos visuais |

### Ciclos autônomos
1. **Ingest** — raw sources → entidades/decisões → 5–15 páginas
2. **Query-as-Write** — insights úteis viram páginas (com confirmação)
3. **Lint** — contradições, órfãos, stale claims (>7d re-verify)
4. **Repair** — reconcilia contradições automaticamente

### TDD (3 suites, dados reais)
```bash
# Ordem: teste → script → ✅
test_entity_creation → vault/entity_create.py → ✅
test_fact_check     → vault/fact_check.py    → ✅
test_lint           → vault/lint.py          → ✅
test_security.py    → vault/security.py     → ✅
vault/seed.py       → primeiro seed real
vault/ingest.py     → primeiro ciclo real
```

### Segurança
- Agente **nunca** escreve fora de `memory/vault/`
- `test_security.py` valida: injeção de paths, escrita fora boundary, frente para trás
- Budget: max 3 verificações Context7 por ingest cycle
- `unverified` confidence: **nunca**写入 vault

### Fase 1 milestones (2 semanas)
- ✅ 8+ entity pages com evidence oficial
- ✅ lint detecta 0 contradições
- ✅ `index.md` e `log.md` atualizam automaticamente
- ✅ nenhum dado escrito fora de `memory/vault/`

### Learning persistido — Fase 1B execution (2026-04-10)
- **Fluxo que funcionou:** implementer → spec reviewer → fix loop → spec re-review → quality review.
- **Gate obrigatório:** nunca avançar para quality review com spec gaps em aberto (corrigir e revalidar antes).
- **Se subagent retornar incompleto/ruim:** assumir no session controller e continuar execução sem bloquear usuário.
- **Evidência mínima de conclusão:** sempre reportar comando e resultado (`python3 -m pytest vault/tests/ -q` → `94 passed`).
- **Spec-sensitive tests:** quando corrigir semântica (ex: orphan=inbound), alinhar asserts dos testes com o comportamento canônico para evitar falsos vermelhos.
- **PR hygiene:** aplicar minor fixes de quality review (unused imports / import placement) antes de abrir PR final.

### Learning persistido — Domain Modeling Living + Vault Schema Fix (2026-04-10)
- **Branch:** `feature/domain-modeling-ingestion-v1`
- **PR:** `https://github.com/living/livy-memory-bot/pull/5`
- **Validação final:** `python3 -m pytest vault/tests/ -q --tb=no` → `413 passed, 1 skipped`.
- **Pipeline E2E:** `python3 -m vault.pipeline --dry-run -v` e `python3 -m vault.pipeline -v` OK; `gaps/orphans after lint = 0/0`.
- **Regra de domínio consolidada:** `part_of` **não** é role canônica; usar apenas `author`, `reviewer`, `commenter`, `participant`, `assignee`, `decision_maker`.
- **Guardrail anti-regressão:** sempre rodar `grep -R "part_of" vault/` antes de fechar task/PR de domínio.
- **Subagent spawn guardrail:** em `runtime=subagent`, usar payload mínimo; não enviar campos ACP-only (`streamTo`, `attachments`, `attachAs`).
- **GH CLI guardrail:** para PRs com markdown/backticks, usar `--body-file` (não inline), evitando command substitution/expansão de shell no corpo.

### Vault Source Schema — Canonical Contract (2026-04-10)

**Schema canônico de `sources` em frontmatter:**
```yaml
sources:
  - source_type: signal_event    # não: type
    source_ref: <url|event-id>   # não: ref
    retrieved_at: 2026-04-10T00:00:00Z  # não: retrieved
    mapper_version: "signal-ingest-v1"    # obrigatório
```

**Migration script:** `scripts/migrate_source_schema.py` — idempotente, com backup automático em `memory/vault/.migration-backup/`.
- Cobertura: decisions/ + entities/ + concepts/
- Compatível retroativamente: parsers de `quality_review` e `domain_lint` aceitam ambos os formatos.

**Regra operacional:** novos writes via `vault/ingest.py` EMITEM schema canônico; parsers de LINT/QUALITY ACEITAM ambos. Migração do acervo histórico via script.

**Validação pós-migração:**
```bash
python3 -m pytest vault/tests/ -q --tb=no  # 420 passed
python3 - <<'PY'
from vault.quality.domain_lint import run_domain_lint
r = run_domain_lint(Path('memory/vault'))
print(r['summary'])  # valid=True, total_errors=0
PY
```

---

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

### test_security.py compatibility

When copying tests between worktrees, verify the API signatures match the target worktree's code:
- `EMBEDDING_CACHE` exists only in `signal-cross-curation`, not in `memory-reconciliation`
- `format_result(meetings, summaries, mode, query)` vs old `(rows, mode, query, similarity)`
- `infer_mode(question, meeting_id)` vs old `(question)` — always pass both args
- `get_headers()` not `get_supabase_headers()`
- default `infer_mode` mode is `"keyword"`, not `"semantic"`

---

## LLM Wiki Auto-Evolutiva — Wave A (2026-04-10)

**Branch:** `feature/wave-a-domain-model-elevation`
**Spec:** `docs/superpowers/specs/2026-04-10-llm-wiki-auto-evolutiva-design.md`
**Plan:** `docs/superpowers/plans/2026-04-10-wave-a-domain-model-elevation-plan.md`

### Ondas (sequenciais puras: A → B → C → D)
- **A:** Confiabilidade do domain model (em progresso) ← ATUAL
- **B:** Cobertura multi-fonte (TLDV + GitHub + claude-mem)
- **C:** Observabilidade + rastreabilidade
- **D:** Autoevolução operacional

### Status Wave A (2026-04-10)
- Design aprovado: ✅
- Plano escrito: ✅
- Branch criada: ✅ (`feature/wave-a-domain-model-elevation`)
- Tasks: 8 (TDD-first, subagent-driven)

### Tasks do Plano
| # | Task | Status |
|---|---|---|
| 1 | Baseline audit + failing contract tests | pending |
| 2 | Script TDD — elevate_to_domain_model | pending |
| 3 | Domain writers em ingest (domain minimum fields) | pending |
| 4 | Lint + quality gate upgrades | pending |
| 5 | PoC migration (1 entity + 2 decisions + 1 concept) | pending |
| 6 | Bulk migration (all vault pages) | pending |
| 7 | Index/log consistency + docs | pending |
| 8 | Final verification + PR readiness | pending |

### Domain Model Contract (vigente)
```yaml
# Decision (domain minimum frontmatter)
---
id_canonical: decision:<slug>
type: decision
confidence: high|medium|low|unverified
sources:              # canônico: source_type/source_ref/retrieved_at/mapper_version
  - source_type: signal_event
    source_ref: <url>
    retrieved_at: 2026-04-10T00:00:00Z
    mapper_version: "signal-ingest-v1"
source_keys: []
lineage:
  run_id: "<uuid>"
  transformed_at: 2026-04-10T00:00:00Z
  mapper_version: "signal-ingest-v1"
  actor: livy-agent
relationships:
  - role: author|reviewer|participant|decision_maker
    entity_ref: person:<id>
---
```
