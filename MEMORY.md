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

## 🗂️ Decisões Registradas

### 2026-04-12 — Crosslink pipeline fix: PR author resolution via `github-login-map.yaml`

Correção do pipeline `vault-crosslink` para resolver autores de PR com mapeamento explícito login→identidade. Resultado validado em produção/desenvolvimento: 729 edges com 31 PR authors resolvidos.
Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-12 — Bot PR filtering, batch cache e identity resolution

Pipeline de crosslink atualizado com filtros para contas de bot, cache em lote e melhorias de resolução de identidade no `crosslink_resolver`/`crosslink_builder`.
Impacto: redução de ruído, deduplicação mais estável e geração de arestas mais confiável.
Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-03 — Whisper Migration: faster-whisper → OmniRoute API-first

`whisper_client.py` reescrito para usar OmniRoute API (groq/whisper) como backend primário. faster-whisper agora opcional. Resolve OOMKilled no VPS.
Topic file: `memory/curated/tldv-pipeline-state.md`

### 2026-04-03 — OmniRoute upgrade 3.4.4 → 3.4.9

Claude Code compatibility. Cascade com 7 modelos em PremiumFirst combo. Config cleanup: minimax-portal removido, PremiumFirst para todos os agentes.
Topic file: `memory/curated/openclaw-gateway.md`

### 2026-04-03 — LLM Rerank + Moderation Guardrails

Design aprovado para reranker via LLM e moderation como pré-hook no `step_enrich`. Implementation plan commitado.
Topic file: `memory/curated/tldv-pipeline-state.md`

### 2026-04-03 — VPS → Living network via Tailscale Node Sharing

Nó `ts-dmz-2.potoroo-ladon.ts.net` (100.92.23.115) conecta VPS à rede Living.
Topic file: `memory/curated/openclaw-gateway.md`

### 2026-04-03 — Super Memória Corporativa (Proposta Robert)

Robert propôs via áudio expandir a memória agêntica para cobrir todo o ecossistema digital da Living: Gmail institucional, Google Drive/Docs, WhatsApp e TLDV.
Análise: infra base (TLDV pipeline + Signal Cross-Curation + ChromaDB) já resolve ~60% do escopo.
Gaps: Google Auth (Domain-wide Delegation), RAG multimodal (RAG-Anything para DOCX/XLSX/PDF), Identity Resolution (cruzar e-mail↔telegram↔tldv).
Topic file: `memory/curated/projeto-super-memoria-robert.md`

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
- Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-18 — Loop de consolidação de research substitui `dream-memory-consolidation`

Decisão: substituir a consolidação legada por um loop de research v1 composto por:
- `research-tldv` (polling de fonte + rebuild de estado derivado, `*/15 * * * *`)
- `research-github` (polling de fonte + rebuild de estado derivado, `*/10 * * * *`)
- `research-trello` (polling de fonte + rebuild de estado derivado, `*/20 * * * *`)
- `research-consolidation` (consolidação diária às 07h BRT)

SSOT permanece em `state/identity-graph/state.json`; arquivos `.research/<source>/state.json` são cache derivado e descartável.
Impacto: consolidação diária passa a refletir pipeline research v1 com lock distribuído, retry policy e rebuild determinístico do estado por fonte.

### 2026-04-19 — PR #19 mergeada: GitHub Rich PR Events + fix de import shadowing

Merge do suporte a eventos ricos de PR GitHub (body/reviews/comments/crosslinks) no pipeline research, com correções de review para acionar enriquecimento no fluxo normal (`pr_merged`) e evitar hipótese com payload vazio.

Validação pós-merge:
- `tests/research/` passando completo: **370 tests**.
- Durante E2E, bug preexistente detectado e corrigido em `master`: `vault/lint/` (package) sombreava `vault/lint.py` (module), quebrando `from vault.lint import ...`.
- Fix aplicado em `vault/lint/__init__.py` com re-export explícito via `importlib` (commit `3ae6fec`).

Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-19 — Hotfix `research-github`: `gh api search/issues` com `-X GET`

Correção aplicada no `vault/research/github_client.py` para forçar método `GET` no endpoint `search/issues`.
Sem `-X GET`, o `gh api` mudava para `POST` ao usar `-f q=...`, retornando `404` e deixando o pipeline com `processed=0`.

Validação:
- `tests/research/test_github_client.py` → **9 passed**
- `tests/research/` → **370 passed**
- Smoke real com `GitHubClient` em `living/livy-memory-bot` → **11 PRs processados** (inclui PR #19)

Commit: `8e1bc76`

Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-19 — PR #18 mergeada: batch-first research clients + cadence wiring

Merge da evolução batch-first do pipeline research com clientes reais para GitHub/TLDV e integração de cadence no loop principal.

**Correções de review implementadas antes do merge:**
1. `research_trello_cron.py`: fallback inválido alinhado para `360` (6h) em vez de `20`.
2. `tldv_client.py`: filtro temporal `updated_at=gte.<cutoff>` aplicado também no first-run (lookback de 7d).
3. `github_client.py`: fluxo robusto em 2 etapas (`search/issues` → `repos/{owner}/{repo}/pulls/{number}`) para garantir `merged_at`, `merged`, `repo` e `author` estáveis.
4. `cadence_manager.py`: contrato documentado explicitamente como **global cadence** (não per-source).
5. Logging estruturado em falhas de clients (sem fail-open silencioso sem evidência).
6. `pipeline.py`: wiring de `record_budget_warning`/`record_healthy_run` + teste de integração 4h↔6h.

**Validação pós-merge:**
- PR #18 mergeada em `master` (`08672fd`)
- `343` testes da suíte research passando (`PYTHONPATH=. pytest tests/research/ -q`)
- Smoke de imports/pipeline/cadence OK

Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-19 — PR #17 mergeada: Evo Wiki Research Phase 2 (Trello + self-healing)

Merge da fase 2 do pipeline de research: streaming de eventos Trello, circuit breaker com thresholds, rollback append-only, board-to-project mapper, e cron `research-trello` registrado.

**Bloqueantes corrigidos no review:**
1. `build_trello_event_key()` agora retorna `trello:{action_id}` (evita colisão cross-source).
2. `state/identity-graph/` adicionado ao `.gitignore` — `self_healing_metrics.json` não é mais versionado.

**Merge commit:** `842852c` (squash) | Branch: `feature/evo-wiki-research-phase2` | 321 testes passando.
Topic file: `memory/curated/livy-memory-agent.md`

### 2026-03-31 — Sistema de Memória como Infraestrutura de Decisão

Decisão: criar agente `@livy_agentic_memory_bot` com memória agêntica de 3 camadas.
Repo: `living/livy-memory-bot`
Arquitetura: claude-mem SQLite (observations) → MEMORY.md + topic files (curated) → HEARTBEAT.md (operational)
Cron original: `dream-memory-consolidation` (07h BRT), `memory-watchdog` (a cada 4h)

### 2026-03-30 — TLDV Pipeline — gw.tldv.io 502 (não é token)

gw.tldv.io retorna 502 Bad Gateway. Token JWT válido até 2026-04-29 (~25 dias). Problema é endpoint de unarchive.
Workaround: `video_archiver.py` diretamente.

### 2026-03-30 — BAT Sev2 Elevado

ConectaBot com 2200 erros Sev2 a cada 6h. Causa: webhook do ConectaBot (comportamento esperado).
Monitorando — não é bug, mas volume elevado.

---

## 🧠 Notas de Consolidação

- Consolidação executada: 2026-04-08 00:02 BRT
- 18 mudanças aplicadas/propostas (stale:TODO / stale:pendente, janela 30-60d)
- 0 arquivos arquivados (>60d threshold)
- Log: `memory/consolidation-log.md`

---

## 📌 Regras Operacionais

1. **LEIA este arquivo primeiro** em cada sessão (memória de longo prazo)
2. **Topic files em `memory/curated/`** contêm contexto detalhado por projeto
3. **Consolidation log** em `memory/consolidation-log.md` — registra mudanças
4. **HEARTBEAT.md** no workspace root — dashboard operacional
5. **Topic files nunca expiram** — se um projeto está ativo, o topic file permanece

---

### 2026-04-19 — PR #20 mergeada: Wiki v2 Phase 1 Foundation

Merge da foundation da Wiki v2: **Memory Core** (invariantes de Claim/Evidence), **Fusion Engine** (confiança, contradição, supersession), **Azure Blob transcripts** (com fallback Supabase segmentado), **Trello/GitHub parsers** evoluídos, **idempotência dual-key** (event_key + content_key), e utilitários operacionais (**shadow run, rollback, replay**).

**Commit:** `a1c0dd3` (squash) | Branch: `feature/wiki-v2-phase1-subagent`

**Validação pós-merge:**
- `PYTHONPATH=. pytest tests/research/ -q` → **439 passed**
- `PYTHONPATH=. pytest tests/vault/ -q` → **90 passed**
- `ResearchPipeline(...)` smoke → OK
- Sem ajustes necessários após merge; todo o conteúdo do PR era consistente com a base.

**Arquitetura nova (módulos entregues):**
- `vault/memory_core/` — models Claim/Evidence/SourceRef/AuditTrail + validação de invariantes
- `vault/fusion_engine/` — confidence scoring, contradição, supersession, engine de fusão
- `vault/capture/azure_blob_client.py` + `vault/capture/supabase_transcript.py` — transcripts segmentados (Azure-first + fallback)
- `vault/research/trello_parsers.py` + `vault/research/github_parsers.py` — parsers normalizados
- `vault/ops/shadow_run.py` + `vault/ops/rollback.py` + `vault/ops/replay_pipeline.py` — operações seguras
- `vault/research/state_store.py` — idempotência dual-key com `processed_content_keys`

**Pontos de atenção documentados (PR body):**
- Parsers ainda geram "claim dicts" de pipeline, não objetos `Claim` do Memory Core (convergência na fase de consolidação)
- Convivência de `vault/research/azure_blob_client.py` (texto raw) vs `vault/capture/azure_blob_client.py` (segments) exige disciplina para evitar drift
- Rollback helper com possível missing import de `json`

Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-19 — WIKI_V2_ENABLED conectado ao ResearchPipeline (rollout auditável)

Implementação do gating real da Wiki v2 no pipeline de research:
- `vault/research/pipeline.py` agora lê `WIKI_V2_ENABLED` via `is_wiki_v2_enabled()`
- `run_started` passa a registrar `wiki_v2_active` no `audit.log`
- comportamento coberto por TDD em `tests/research/test_pipeline_wiki_v2_flag.py` (4 testes)

Validação:
- `PYTHONPATH=. pytest tests/research/test_pipeline_wiki_v2_flag.py -q` → **4 passed**
- subset pipeline (`tldv/github/trello + wiki_v2_flag`) → **61 passed**
- suíte canônica: `PYTHONPATH=. pytest tests/research/ -q` → **443 passed**

Commit: `d81eb7e`
Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-19 — PR #21 mergeada: Weekly Insights claims-first com HTML group attachment

Merge da evolução do weekly insights para formato claims-first com entrega dual-channel:
- `vault/insights/claim_inspector.py` — extrai e filtra claims do SSOT (`state/identity-graph/state.json`)
- `vault/insights/renderers.py` — renderiza claims em formato markdown (DM pessoal) e HTML (documento grupo)
- `vault/crons/vault_insights_weekly_generate.py` — script de geração com dedupe, fallback markdown e entrega Telegram
- Entrega dual: DM pessoal (markdown, 7426291192) + documento HTML no grupo (-5158607302)

**Commits:** `dbf9149` (PR #21) + `7c86f4b` (hotfix PR #22)

**Validação pós-merge:**
- `pytest vault/tests/test_vault_insights_weekly_generate.py vault/tests/test_renderers.py vault/tests/test_claim_inspector.py -q` → **44 passed**
- E2E produção: DM enviado para 7426291192, documento HTML enviado para -5158607302 ✅

**Bug encontrado na validação E2E:**
- `vault_insights_weekly_generate.py` resolvia token via `.env` (`TELEGRAM_TOKEN`) que aponta para `@livy_chat_bot`, não `@livy_agentic_memory_bot`
- Resultado: `sendDocument` ao grupo falhava com `Bad Request: chat not found`
- Fix: `_resolve_bot_token()` com precedência: `TELEGRAM_BOT_TOKEN` → `TELEGRAM_MEMORY_BOT_TOKEN` → OpenClaw config `channels.telegram.accounts.memory.botToken` → `TELEGRAM_TOKEN`
- Fix commitado em PR #22 (`7c86f4b`)

Topic file: `memory/curated/livy-memory-agent.md`

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

Review attention points documentados no docstring de `apply_merge_to_ssot`:
- `decision['contradiction']` deve ser injetado pelo pipeline chamador (apply_decision não popula)
- `merge_id` gap vs spec (usa hypothesis vs claim_ids+reason — follow-up de alinhamento com pipeline)
- `lock_path` documentado como obrigatório por callers

**Fix orthogonal encontrado durante E2E — GitHub search cross-repo noise:**
- Bug: `gh api search/issues` com `repo:living/repo AND org:living` retorna PRs de múltiplos repos na org (comportamento inesperado do Search API com ambos os qualificadores)
- Fix: remover `org:living` do query; adicionar filtro defensivo por `repository_url` normalizado em `_search_merged_pr_summaries`
- Commit `e645c42` pushado para `origin/master`
- Validação: research_github cron sem 404 pull lookups no audit log

**Validação E2E pós-merge:**
- `PYTHONPATH=. pytest tests/research/ -q` → **476 passed**
- E2E com `apply_decision` + `apply_merge_to_ssot` em contexto real: idempotência ✅, contradição ✅, lock+persistência ✅
- Crons E2E (github/trello/tldv): todos `status=success`

Topic file: `memory/curated/livy-memory-agent.md`

### 2026-04-22 — PR #24 mergeada: Enriched Claims Rollout (Tasks 1–9)

Merge da evolução de claims com o pipeline de research v1. Decisões técnicas e linkages agoraходят com `needs_review`/`review_reason`, deduplicação semântica via `decision_key`/`linkage_key`, guardrails de qualidade, e consolidação expandida com KPIs.

**Commit:** `fd0f9ac` (squash merge PR #24) | Branch: `feature/enriched-claims-impl`

**Validação pós-merge:**
- `PYTHONPATH=. pytest tests/research/ -q` → **545 passed**
- `PYTHONPATH=. pytest tests/vault/ -q` → **140 passed**
- 4 crons smoke: github/tldv/trello/consolidation → todos `status=success`
- claim distribution: `status:97.4% / linkage:2.6% / decision:0%` (baseline SSOT pré-existente)
- quality guardrail: `pct_decision=0`, `pct_linkage=2.6` — abaixo do threshold `>=40%` combinado; 1º ciclo de alerta, sem emissão (threshold: 2 ciclos consecutivos)

**Arquitetura entregue:**
- `vault/memory_core/models.py` — `needs_review: bool`, `review_reason: str|None` em `Claim`
- `vault/research/trello_client.py` — `get_card_comments()`, `get_card_checklists()`
- `vault/research/trello_parsers.py` — extração de decision via linguagem normativa + comments/checklists
- `vault/research/github_parsers.py` — linkage `from/to_entity` + decisões por linguagem normativa restritiva
- `vault/research/tldv_client.py` — extraction de `summaries.decisions` + regex fallback
- `vault/fusion_engine/confidence.py` — `+0.15` por `evidence_ids`, `-0.10` por regex fallback, `needs_review` calibrado
- `vault/fusion_engine/supersession.py` — proteção decision→decision por similaridade textual `>0.7` ou `supersession_reason` explícito; bloqueia `status→decision`
- `vault/research/state_store.py` — `decision_key` + `linkage_key` como gates secundários de deduplicação (complementares a `content_key`)
- `vault/crons/research_consolidation_cron.py` — KPIs `%decision`, `%linkage`, `%needs_review`, `%with_evidence`; alerta após 2 ciclos ruins consecutivos
- `tests/vault/test_claim_model.py`, `tests/vault/ops/test_quality_guardrails.py`, `tests/research/test_semantic_dedupe_keys.py` — 26+ testes novos

**Gaps esperados (não bloqueantes):**
- Claim distribution `decision:0%` + `linkage:2.6%` — abaixo da meta `>=40%` combinado. Quality guardrail ativado após 2 ciclos ruins. Baseline reflete SSOT pré-existente sem enriquecimento de decisões/linkages; o próximo ciclo de cron com dados novos vai começar a preencher.
- `decision_key`/`linkage_key` counts = 0 no state compaction — as chaves foram populadas nos runs de smoke mas não nos dados históricos do SSOT (comportamento esperado para base legada)

Topic file: `memory/curated/livy-memory-agent.md`

_Last updated: 2026-04-22_
