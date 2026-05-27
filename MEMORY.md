# MEMORY.md — Livy Memory Agent Curated Index

> **Index de contexto curado.** Este arquivo é a memória de longo prazo do agente Livy Memory.
> Decisões técnicas, contexto de projetos, padrões operacionais.

---

## 🏗️ Arquitetura de Memória Living

| Camada | Fonte | Path |
|---|---|---|
| 1 — Observations | claude-mem SQLite | `~/.claude-mem/claude-mem.db` |
| 2 — Curated | Topic files | `memory/curated/*.md` |
| 3 — Operational | HEARTBEAT + logs | `HEARTBEAT.md`, `memory/consolidation-log.md` |

---

## 📁 Topic Files

### Projetos

| Projeto | Topic File | Status |
|---|---|---|
| Forge Platform | `memory/curated/forge-platform.md` | em progresso |
| BAT Observability | `memory/curated/bat-conectabot-observability.md` | monitorando |
| Delphos Video Vistoria | `memory/curated/delphos-video-vistoria.md` | OK |
| TLDV Pipeline | `memory/curated/tldv-pipeline-state.md` | ativo_com_bugs (whisper migrado; gw.tldv.io 502 persiste) |
| Super Memória Corporativa | `memory/curated/projeto-super-memoria-robert.md` | proposta (Robert, 2026-04-03) |
| livy-evo | `memory/curated/livy-evo.md` | conforme cronograma |

### Agentes & Tools

| Assunto | Topic File | Status |
|---|---|---|
| Livy Memory Agent | `memory/curated/livy-memory-agent.md` | ativo |
| OpenClaw Gateway | `memory/curated/openclaw-gateway.md` | ativo |
| claude-mem | `memory/curated/claude-mem-observations.md` | ativo |

---

## 🗂️ Decisões Registradas (cronológicas invertida)

### 2026-05-27 — vault_search_transcripts: busca em transcripts Azure Blob

Novo módulo `azure_transcript_search.py` e tool `vault_search_transcripts` no MCP server.

- `get_transcript(meeting_id)` — fetch completo do Azure Blob (`.transcript.tldv.json`)
- `extract_speakers(meeting_id)` — participantes com contagem de segmentos
- `search_transcripts(query, limit)` — busca full-text em todos os 125 transcripts (AZURE_STORAGE_ACCOUNT=livingnetopenclawstorage, container=living-meeting-hub)
- `format_transcript_full()` — texto legível com speaker labels e timestamps

**Bugs corrigidos:**
- `speaker=None` causava `AttributeError` na busca — agora trata `None` como string vazia

**MCP tool:** `vault_search_transcripts(query, limit, full)` — ~0.5s para buscar em todos os transcripts

```
mcporter call vault.vault_search_transcripts query="Lincoln" limit:=3
mcporter call vault.vault_search_transcripts query="compliance" limit:=2 full:=true
```

Commits: `fba06ec` + `9e35b5e` | Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-05-25 — QW-2 Pipeline: Real Mode + April Backfill

**Status:** Real mode activo desde 2026-05-25. Pipeline extrai de TLDV + GitHub + Trello para topic files em `memory/vault/decisions/`.

**QW-2 real mode:**
- `qw2-daily` cron (seg-sex 07h BRT) executa pipeline real com consolidate + MEMORY + Honcho index
- `qw3-callback` cron ( */15 9-18 * * 1-5) processa approve/reject via polling Telegram
- `qw3-dm-poller` backup para comandos /qw2approve /qw2reject

**Bugs corrigidos durante validação E2E:**
- `fetch_tldv`: `fetch_meeting()` retorna `{}` para meetings sem transcript — o campo `decisions`/`topics` está em `fetch_summaries(meeting_id)`
- `fetch_tldv`: usava campo `id` em vez de `meeting_id` no objeto meeting
- `fetch_tgithub` (QW-2): lia `event["payload"]` inexistente — GitHubClient retorna eventos normalizados diretamente
- GitHubClient: tinha 4 repos hardcoded + 1 query/repo (rate limit) — refeito para 1 query org-wide com `is:pr merged:>DATE org:living --paginate`
- `honcho_indexer`: `observed_id` deve ser `HONCHO_AGENT_PEER` ('agent-memory-agent'), não `source_type` ('github'/'trello'/'tldv') — 404 'Peer not found'

**April backfill (2026-05-25):**
- Script: `vault/qw2/backfill_tldv_april.py` — usa Supabase directamente para绕y TLDV API timeout
- 28 meetings Abril 1-26; 40 decisions extraídas; 16 escritas; 24 dedupe (já existiam de runs anteriores)
- Topic files: +11 entries `livy-memory-agent.md` (Abr 1,6,7,8,9,10,13,15,16,22,24), +1 `bat-conectabot-observability.md` (Abr 8)
- Honcho indexed: 73 decisions totais (20 delphos + 6 infra + 13 bat + 34 livy + 7 general)

**Scripts:** `vault/qw2/run.py` + `router.py` + `writer.py` + `honcho_indexer.py` + `consolidate.py` + `update_memory_index.py` + crons (`qw2_daily_cron.py`, `qw3_callback_cron.py`, `qw3_dm_poller_cron.py`)

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-05-23 — Backfill lessons: Mai 7–23 (GitHub 98 / Trello 29 / TLDV 34)

Extensão do backfill W1-W5 para o período Mai 7–23 via `honcho_capture.py` com as 3 fontes:

| Fonte | Lições | Detalhe |
|---|---|---|
| GitHub PRs | 98 | 8 repos (delphos-svd 18, bot-ai-api 18, bot-ai-app 10, RetailAuditRulesDashboard 8, insight-funds 11, elcano-robo-ocr 1, RetailAuditInfraDashboard 3, llm-rag-api 1); cycle_time em frontmatter |
| Trello cards | 29 | effort (custom fields) + pr_refs preenchidos; 74 skipped (já existentes do W1-W5) |
| TLDV meetings | 34 | per-meeting extraction; reuniões de Abr 24 – Mai 21 |

**Todos indexados ao Honcho** via `POST /v3/workspaces/{id}/conclusions`.

Commit: `0659bf1` | Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-05-23 — Crosslink Trello ↔ GitHub

Script `build_trello_pr_crosslink.py` cria edges em `memory/vault/relationships/trello-pr.json`:
- Trello → PR: via `pr_refs` nas descrições dos cards
- PR → Trello: via URLs `trello.com/c/{card_id}` nos bodies de PR

**Resultado:** 0 edges (cards Trello não têm `pr_refs` preenchidos; PR bodies não têm URLs Trello). Crosslink existe como estrutura — basta preencher `pr_refs` nos cards ou Trello URLs nos PRs para activar.

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-05-23 — ETL honcho_capture: cycle_time + effort + pr_refs + 99 repos auto-discover

Evolução do ETL `honcho_capture.py` para extração rica de lições:

**Novos campos extraídos:**
- `cycle_time` — tempo entre primeiro commit e merge (GitHub `createdAt` → `mergedAt`). Formato legível: `19m`, `4h 30m`, `2d 5h`.
- `effort` — custom field `Effort` (number) dos cards Trello quando preenchido. Value ou `Not specified`.
- `pr_refs` — URLs GitHub extraídas das descrições dos cards Trello (regex `github.com/([\w-]+)/([\w.-]+)/pull/(\d+)` → `org/repo#N`).

**Bugs corrigidos:**
- `gh pr list --json` com campo inexistente `commentsCount` → agora usa só `number,title,body,mergedAt,url,labels,createdAt`
- `count_merged_prs` não propagava `after`/`before` → agora propaga para `get_merged_prs`
- `get_merged_prs` com range explícito `after`+`before` tinha `cutoff` a bloquear → cutoff é `None` quando há range explícito
- `get_closed_issues` mesmo problema de cutoff condicional → corrigido

**Auto-discover de repos:** `list_org_repos()` descobre todos os 99 repos activos da org `living` em vez de lista hardcoded.

**Resultado:** backfill completo W1-W5 (Abr 1 – Mai 7):
- 40 PR lessons com `cycle_time` (todos os repos living)
- 98+ Trello lessons com `effort` + `pr_refs`
- 0 PRs em W1 (primeiro merge: 2026-04-07 #2, 2026-04-10 #3)
- 0 cards Trello em W1 (primeira activity: 2026-04-08)

Commits: `7026794` (cycle_time+effort+pr_refs), `a98a9fc` (lessons W3)

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-05-22 — Stale thresholds: per-entity-type (meetings 60d, cards 90d, persons/prs 60d)

Thresholds anteriores: 30d para todos os tipos de entity.
Resultado: 347 stale (meetings 70 + persons 37 + prs 39 + cards 201).
Decisão: thresholds por tipo — meeting:60d, card:90d, person:60d, pr:60d.
Resultado: 347 stale → 0 stale.
Commits: `9f57022` (stale thresholds) + `38c12c3` (archive exclusion) + `2ec4399` (regex fix).

---

### 2026-05-22 — Person variants: 6 quarantine arquivados

6 entities em quarantine (.archive/quarantine-20260522/):
- andre.chaves, bianca_porcari_corraca, enisia.soares, lincolnqjunior,
  monique.ceciliano, robert.urech
Motivo: todas representavam persons já indexados (TLDV person-id variants ou confidence variants).
Emails das variants merged nos canonicals.
Resultado: 6 orphans → 0 orphans.

---

### 2026-04-22 — PR #24 mergeada: Enriched Claims Rollout (Tasks 1–9)

Merge da evolução de claims com o pipeline de research v1. Decisões técnicas e linkages agora incluem `needs_review`/`review_reason`, deduplicação semântica via `decision_key`/`linkage_key`, guardrails de qualidade, e consolidação expandida com KPIs.

**Commit:** `fd0f9ac` (squash merge PR #24) | Branch: `feature/enriched-claims-impl`

**Validação pós-merge:**
- `PYTHONPATH=. pytest tests/research/ -q` → **545 passed**
- `PYTHONPATH=. pytest tests/vault/ -q` → **140 passed**
- 4 crons smoke: github/tldv/trello/consolidation → todos `status=success`
- claim distribution: `status:97.4% / linkage:2.6% / decision:0%` (baseline SSOT pré-existente)
- quality guardrail: `pct_decision=0`, `pct_linkage=2.6` — abaixo do threshold `>=40%` combinado; 1º ciclo de alerta, sem emissão

**Arquitetura entregue:**
- `vault/memory_core/models.py` — `needs_review: bool`, `review_reason: str|None` em `Claim`
- `vault/research/trello_client.py` — `get_card_comments()`, `get_card_checklists()`
- `vault/research/trello_parsers.py` — extração de decision via linguagem normativa + comments/checklists
- `vault/research/github_parsers.py` — linkage `from/to_entity` + decisões por linguagem normativa restritiva
- `vault/research/tldv_client.py` — extraction de `summaries.decisions` + regex fallback
- `vault/fusion_engine/confidence.py` — `+0.15` por `evidence_ids`, `-0.10` por regex fallback, `needs_review` calibrado
- `vault/fusion_engine/supersession.py` — proteção decision→decision por similaridade textual `>0.7` ou `supersession_reason` explícito; bloqueia `status→decision`
- `vault/research/state_store.py` — `decision_key` + `linkage_key` como gates secundários de deduplicação
- `vault/crons/research_consolidation_cron.py` — KPIs `%decision`, `%linkage`, `%needs_review`, `%with_evidence`; alerta após 2 ciclos ruins consecutivos

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — PR #23 mergeada: Self-Healing Apply V2 + Hotfix GitHub cross-repo noise

**PR #23 — Self-Healing Apply V2** (`feature/self-healing-apply-v2` → `master`):

Merge squash commit `cea58c8`. Infraestrutura de self-healing v2 pronta para integração com pipeline:
- `apply_decision()` — política v2 strict (>=0.85 auto-apply, 0.45–0.84 queued, <0.45 dropped)
- `apply_merge_to_ssot()` — persistência em `state/identity-graph/state.json` com lock + idempotência + prune 180d
- Circuit breaker v2 — 3-tier (monitoring → write_paused → global_paused), reset automático após 3 clean runs
- `merge_id` determinístico de `(hypothesis, confidence, source)` via SHA256
- Schema migration v1→v2 in-place
- Append-only rollback via `vault/logs/experiments.jsonl`
- **50 testes** cobrindo policy v1/v2, idempotência, lock, pruning, schema upgrade

**Fix orthogonal — GitHub search cross-repo noise:**
- Bug: `gh api search/issues` com `repo:living/repo AND org:living` retorna PRs de múltiplos repos na org
- Fix: remover `org:living` da query; filtro defensivo por `repository_url` normalizado em `_search_merged_pr_summaries`
- Commit `e645c42` pushado para `origin/master`

**Validação E2E pós-merge:**
- `PYTHONPATH=. pytest tests/research/ -q` → **476 passed**
- Crons E2E (github/trello/tldv): todos `status=success`

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — PR #21 mergeada: Weekly Insights claims-first com HTML group attachment

Merge da evolução do weekly insights para formato claims-first com entrega dual-channel:
- `vault/insights/claim_inspector.py` — extrai e filtra claims do SSOT
- `vault/insights/renderers.py` — markdown (DM) + HTML (documento grupo)
- `vault/crons/vault_insights_weekly_generate.py` — geração com dedupe + entrega Telegram
- Entrega dual: DM pessoal (7426291192) + documento HTML no grupo (-5158607302)

**Commits:** `dbf9149` (PR #21) + `7c86f4b` (hotfix PR #22 — token Telegram errado)

**Validação pós-merge:**
- `pytest vault/tests/test_vault_insights_weekly_generate.py vault/tests/test_renderers.py vault/tests/test_claim_inspector.py -q` → **44 passed**
- E2E produção: DM + HTML no grupo ✅

**Bug:** `vault_insights_weekly_generate.py` usava `TELEGRAM_TOKEN` pointing to `@livy_chat_bot` em vez de `@livy_agentic_memory_bot`
Fix: `_resolve_bot_token()` com precedência: `TELEGRAM_BOT_TOKEN` → `TELEGRAM_MEMORY_BOT_TOKEN` → OpenClaw config → `TELEGRAM_TOKEN`

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — PR #20 mergeada: Wiki v2 Phase 1 Foundation

**Commit:** `a1c0dd3` (squash) | Branch: `feature/wiki-v2-phase1-subagent`

**Validação pós-merge:**
- `PYTHONPATH=. pytest tests/research/ -q` → **439 passed**
- `PYTHONPATH=. pytest tests/vault/ -q` → **90 passed**
- `ResearchPipeline(...)` smoke → OK

**Arquitetura entregue:**
- `vault/memory_core/` — models Claim/Evidence/SourceRef/AuditTrail + validação de invariantes
- `vault/fusion_engine/` — confidence scoring, contradição, supersession, engine de fusão
- `vault/capture/azure_blob_client.py` + `vault/capture/supabase_transcript.py` — transcripts segmentados (Azure-first + fallback)
- `vault/research/trello_parsers.py` + `vault/research/github_parsers.py` — parsers normalizados
- `vault/ops/shadow_run.py` + `vault/ops/rollback.py` + `vault/ops/replay_pipeline.py` — operações seguras
- `vault/research/state_store.py` — idempotência dual-key com `processed_content_keys`

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — WIKI_V2_ENABLED conectado ao ResearchPipeline (rollout auditável)

Implementação do gating real da Wiki v2 no pipeline de research:
- `vault/research/pipeline.py` agora lê `WIKI_V2_ENABLED` via `is_wiki_v2_enabled()`
- `run_started` passa a registrar `wiki_v2_active` no `audit.log`
- comportamento coberto por TDD em `tests/research/test_pipeline_wiki_v2_flag.py` (4 testes)

Validação:
- `PYTHONPATH=. pytest tests/research/test_pipeline_wiki_v2_flag.py -q` → **4 passed**
- subset pipeline → **61 passed**
- suíte canônica: `PYTHONPATH=. pytest tests/research/ -q` → **443 passed**

Commit: `d81eb7e` | Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — Wiki v2 produção: github + trello + tldv no FusionEngine pipeline

Commit `23e6019` completa a migração wiki v2 para as 3 fontes:
- `WIKI_V2_ENABLED=true` routing (`github`, `trello`, `tldv`) → FusionEngine
- github: `pr_to_claims()` (status/approval/linkage/tag/context)
- trello: `parse_trello_card()` + `card_to_claims()`
- tldv: claim de meeting/status a partir de `fetch_meeting()`
- `fuse()` detecta contradições e aplica supersession contra state claims existente
- Fused claims persistidos em `state/identity-graph/state.json` (key: `claims`)
- Blobs de claim em `memory/vault/claims/<claim_id>.md`
- Old markdown path preservado quando flag=false (compatibilidade)
- Rollback: `gateway config.patch(features.wiki_v2.enabled=false)`

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — PR #19 mergeada: GitHub Rich PR Events + fix de import shadowing

Merge do suporte a eventos ricos de PR GitHub (body/reviews/comments/crosslinks) no pipeline research, com correções de review para acionar enriquecimento no fluxo normal (`pr_merged`) e evitar hipótese com payload vazio.

**Validação pós-merge:**
- `tests/research/` passando completo: **370 tests**
- Bug preexistente corrigido em `master`: `vault/lint/` (package) sombreava `vault/lint.py` (module), quebrando `from vault.lint import ...`
- Fix aplicado em `vault/lint/__init__.py` com re-export explícito via `importlib` (commit `3ae6fec`)

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — Hotfix `research-github`: `gh api search/issues` com `-X GET`

Correção aplicada no `vault/research/github_client.py` para forçar método `GET` no endpoint `search/issues`.
Sem `-X GET`, o `gh api` mudava para `POST` ao usar `-f q=...`, retornando `404` e deixando o pipeline com `processed=0`.

**Validação:**
- `tests/research/test_github_client.py` → **9 passed**
- `tests/research/` → **370 passed**
- Smoke real: **11 PRs processados** (inclui #19)

Commit: `8e1bc76` | Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — PR #18 mergeada: batch-first research clients + cadence wiring

Merge da evolução batch-first do pipeline research com clientes reais para GitHub/TLDV e integração de cadence no loop principal.

**Correções de review implementadas antes do merge:**
1. `research_trello_cron.py`: fallback inválido alinhado para `360` (6h) em vez de `20`
2. `tldv_client.py`: filtro temporal `updated_at=gte.<cutoff>` aplicado também no first-run (lookback de 7d)
3. `github_client.py`: fluxo robusto em 2 etapas (`search/issues` → `repos/{owner}/{repo}/pulls/{number}`) para garantir `merged_at`, `merged`, `repo` e `author` estáveis
4. `cadence_manager.py`: contrato documentado explicitamente como **global cadence** (não per-source)
5. Logging estruturado em falhas de clients (sem fail-open silencioso sem evidência)
6. `pipeline.py`: wiring de `record_budget_warning`/`record_healthy_run` + teste de integração 4h↔6h

**Validação pós-merge:**
- PR #18 mergeada em `master` (`08672fd`)
- `PYTHONPATH=. pytest tests/research/ -q` → **343 passed**
- Smoke de imports/pipeline/cadence OK

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-19 — PR #17 mergeada: Evo Wiki Research Phase 2 (Trello + self-healing)

Merge da fase 2 do pipeline de research: streaming de eventos Trello, circuit breaker com thresholds, rollback append-only, board-to-project mapper, e cron `research-trello` registrado.

**Bloqueantes corrigidos no review:**
1. `build_trello_event_key()` agora retorna `trello:{action_id}` (evita colisão cross-source)
2. `state/identity-graph/` adicionado ao `.gitignore` — `self_healing_metrics.json` não é mais versionado

**Merge commit:** `842852c` (squash) | Branch: `feature/evo-wiki-research-phase2` | 321 testes passando.

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-18 — Loop de consolidação de research substitui `dream-memory-consolidation`

Decisão: substituir a consolidação legada por um loop de research v1 composto por:
- `research-tldv` (polling de fonte + rebuild de estado derivado, `*/15 * * * *`)
- `research-github` (polling de fonte + rebuild de estado derivado, `*/10 * * * *`)
- `research-trello` (polling de fonte + rebuild de estado derivado, `*/20 * * * *`)
- `research-consolidation` (consolidação diária às 07h BRT)

SSOT permanece em `state/identity-graph/state.json`; arquivos `.research/<source>/state.json` são cache derivado e descartável.

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-12 — Crosslink pipeline fix: PR author resolution via `github-login-map.yaml`

Correção do pipeline `vault-crosslink` para resolver autores de PR com mapeamento explícito login→identidade. Resultado validado em produção/desenvolvimento: 729 edges com 31 PR authors resolvidos.

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-12 — Bot PR filtering, batch cache e identity resolution

Pipeline de crosslink atualizado com filtros para contas de bot, cache em lote e melhorias de resolução de identidade no `crosslink_resolver`/`crosslink_builder`.
Impacto: redução de ruído, deduplicação mais estável e geração de arestas mais confiável.

Topic file: `memory/curated/livy-memory-agent.md`

---

### 2026-04-03 — Whisper Migration: faster-whisper → OmniRoute API-first

`whisper_client.py` reescrito para usar OmniRoute API (groq/whisper) como backend primário. faster-whisper agora opcional. Resolve OOMKilled no VPS.

Topic file: `memory/curated/tldv-pipeline-state.md`

---

### 2026-04-03 — OmniRoute upgrade 3.4.4 → 3.4.9

Claude Code compatibility. Cascade com 7 modelos em PremiumFirst combo. Config cleanup: minimax-portal removido, PremiumFirst para todos os agentes.

Topic file: `memory/curated/openclaw-gateway.md`

---

### 2026-04-03 — LLM Rerank + Moderation Guardrails

Design aprovado para reranker via LLM e moderation como pré-hook no `step_enrich`. Implementation plan commitado.

Topic file: `memory/curated/tldv-pipeline-state.md`

---

### 2026-04-03 — VPS → Living network via Tailscale Node Sharing

Nó `ts-dmz-2.potoroo-ladon.ts.net` (100.92.23.115) conecta VPS à rede Living.

Topic file: `memory/curated/openclaw-gateway.md`

---

### 2026-04-03 — Super Memória Corporativa (Proposta Robert)

Robert propôs via áudio expandir a memória agêntica para cobrir todo o ecossistema digital da Living: Gmail institucional, Google Drive/Docs, WhatsApp e TLDV.

Análise: infra base (TLDV pipeline + Signal Cross-Curation + ChromaDB) já resolve ~60% do escopo.
Gaps: Google Auth (Domain-wide Delegation), RAG multimodal (RAG-Anything para DOCX/XLSX/PDF), Identity Resolution (cruzar e-mail↔telegram↔tldv).

Topic file: `memory/curated/projeto-super-memoria-robert.md`

---

### 2026-03-31 — Sistema de Memória como Infraestrutura de Decisão

Decisão: criar agente `@livy_agentic_memory_bot` com memória agêntica de 3 camadas.
Repo: `living/livy-memory-bot`
Arquitetura: claude-mem SQLite (observations) → MEMORY.md + topic files (curated) → HEARTBEAT.md (operational)
Cron original: `dream-memory-consolidation` (07h BRT), `memory-watchdog` (a cada 4h)

---

### 2026-03-30 — TLDV Pipeline — gw.tldv.io 502 (não é token)

gw.tldv.io retorna 502 Bad Gateway. Token JWT válido até 2026-04-29 (~25 dias). Problema é endpoint de unarchive.
Workaround: `video_archiver.py` diretamente.

---

### 2026-03-30 — BAT Sev2 Elevado

ConectaBot com 2200 erros Sev2 a cada 6h. Causa: webhook do ConectaBot (comportamento esperado).
Monitorando — não é bug, mas volume elevado.

---

## 📌 Regras Operacionais

1. **LEIA este arquivo primeiro** em cada sessão (memória de longo prazo)
2. **Topic files em `memory/curated/`** contêm contexto detalhado por projeto
3. **Consolidation log** em `memory/consolidation-log.md` — registra mudanças
4. **HEARTBEAT.md** no workspace root — dashboard operacional
5. **Topic files nunca expiram** — se um projeto está ativo, o topic file permanece
6. **Decisões em ordem cronológica invertida** (mais recente primeiro)

---

## 🧠 Notas de Consolidação

| Data | Alteração |
|---|---|
| 2026-05-22 03:05 UTC | stale thresholds 60d/90d (347 stale → 0); 6 person variants quarentenados+arquivados; .archive exclusion em vault-lint; Commits: 9f57022 + 38c12c3 + 2ec4399 |
| 2026-05-27 | Consolidação: removeduplicatas PR#20/21/23/24; addedecision azure_transcript_search (fba06ec+9e35b5e); normalized QW-2 tables |

_Last updated: 2026-05-27_
