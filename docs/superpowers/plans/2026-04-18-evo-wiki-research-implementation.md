# Evo Wiki Research (Fase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar a Fase 1 do Evo Wiki Research no `workspace-livy-memory`, com crons especializados (TLDV + GitHub), identity graph append-only em `state/identity-graph/`, dedupe idempotente por `event_key`, governança/auditoria e self-healing em modo read-only.

**Architecture:** Criar um módulo de orquestração de research orientado a polling por cron que normaliza eventos, resolve identidades com regras explícitas (email-first + contexto), aplica enriquecimento em camadas permitidas, e persiste estado canônico único (`state/identity-graph/state.json`). O sistema usa lock por fonte (`flock`) com cleanup de stale lock, retry/backoff com status `pending_retry/exhausted`, e consolidação diária que substitui `dream-memory-consolidation`.

**Tech Stack:** Python 3, pytest, módulos `vault/ingest`, `vault/domain`, `vault/crons`, estado JSON/JSONL append-only, OpenClaw cron.

---

## File Structure (alvos desta fase)

### Create
- `state/identity-graph/state.json` (seed inicial + cursores por fonte)
- `state/identity-graph/people.jsonl` (append-only)
- `state/identity-graph/projects.jsonl` (append-only)
- `vault/research/__init__.py`
- `vault/research/event_key.py` (geração/canonicalização de `event_key`)
- `vault/research/state_store.py` (SSOT read/write + retenção 180d)
- `vault/research/lock_manager.py` (flock + stale lock cleanup)
- `vault/research/retry_policy.py` (`pending_retry/exhausted`)
- `vault/research/source_priority.py` (GitHub > TLDV > Trello)
- `vault/research/identity_resolver.py` (email-first + fallback contexto)
- `vault/research/archive_guard.py` (3 guardrails de archive)
- `vault/research/pipeline.py` (11 passos do spec)
- `vault/crons/research_tldv_cron.py`
- `vault/crons/research_github_cron.py`
- `vault/crons/research_consolidation_cron.py`
- `tests/research/test_event_key.py`
- `tests/research/test_state_store.py`
- `tests/research/test_lock_manager.py`
- `tests/research/test_retry_policy.py`
- `tests/research/test_identity_resolver.py`
- `tests/research/test_conflict_resolution.py`
- `tests/research/test_archive_guard.py`
- `tests/research/test_pipeline_tldv.py`
- `tests/research/test_pipeline_github.py`
- `tests/research/test_consolidation_loop.py`

### Modify
- `vault/crons/__init__.py` (expor novos crons)
- `HEARTBEAT.md` (seção jobs/alertas dos novos crons)
- `MEMORY.md` (decisão de substituição do dream-memory-consolidation após go-live)
- `.gitignore` (garantir política correta de arquivos state/lock)

---

### Task 1: Bootstrap do módulo `vault/research` com TDD

**Files:**
- Create: `vault/research/__init__.py`, `vault/research/event_key.py`
- Test: `tests/research/test_event_key.py`

- [ ] **Step 1: Write failing tests para `event_key`**
```python
def test_build_event_key_without_action_id():
    assert build_event_key("github", "pr_merged", "123") == "github:pr_merged:123"


def test_build_event_key_with_action_id():
    assert build_event_key("github", "review_submitted", "123", "a1") == "github:review_submitted:123:a1"
```

- [ ] **Step 2: Run tests (deve falhar)**
Run: `pytest tests/research/test_event_key.py -v`
Expected: FAIL (módulo/função inexistente)

- [ ] **Step 3: Implement minimal `build_event_key`**

- [ ] **Step 4: Run tests (deve passar)**
Run: `pytest tests/research/test_event_key.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/__init__.py vault/research/event_key.py tests/research/test_event_key.py
git commit -m "feat(research): add event_key builder with tests"
```

### Task 2: SSOT state store + retenção 180d

**Files:**
- Create: `vault/research/state_store.py`
- Create: `state/identity-graph/state.json`
- Test: `tests/research/test_state_store.py`

- [ ] **Step 1: Write failing tests para leitura/escrita de state canônico**
- [ ] **Step 2: Testar retenção de `processed_event_keys` (drop >180d)**
- [ ] **Step 3: Implementar API mínima**
  - `load_state()`
  - `save_state()`
  - `upsert_processed_event_key(source, event_key, event_at)`
  - `compact_processed_keys(retention_days=180)`
- [ ] **Step 4: Run tests**
Run: `pytest tests/research/test_state_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add state/identity-graph/state.json vault/research/state_store.py tests/research/test_state_store.py
git commit -m "feat(research): add canonical state store with 180d retention"
```

### Task 3: Lock manager com stale lock cleanup

**Files:**
- Create: `vault/research/lock_manager.py`
- Test: `tests/research/test_lock_manager.py`

- [ ] **Step 1: Write failing tests**
Casos:
- lock livre → acquire
- lock com PID vivo (<TTL) → skip
- lock stale (PID morto ou >TTL) → reaproveita

- [ ] **Step 2: Implementar lock via `flock` + metadata (`pid`, `start_ts`)**
- [ ] **Step 3: Run tests**
Run: `pytest tests/research/test_lock_manager.py -v`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add vault/research/lock_manager.py tests/research/test_lock_manager.py
git commit -m "feat(research): add lock manager with stale lock cleanup"
```

### Task 4: Retry policy + schema `pending_retry/exhausted`

**Files:**
- Create: `vault/research/retry_policy.py`
- Test: `tests/research/test_retry_policy.py`

- [ ] **Step 1: Write failing tests para 429/5xx/401/403/timeout**
- [ ] **Step 2: Implement policy**
  - 429: 1/2/4/8m (max 3)
  - 5xx: 30/60/120s (max 3)
  - 401/403: no-retry
  - timeout: retry imediato 1x + policy 5xx
- [ ] **Step 3: Persistir campos mínimos de erro**
  - `retry_count`, `next_retry_at`, `last_error`, `last_attempt_at`, `status`
- [ ] **Step 4: Run tests**
Run: `pytest tests/research/test_retry_policy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/retry_policy.py tests/research/test_retry_policy.py
git commit -m "feat(research): add retry policy and pending_retry schema"
```

### Task 5: Resolver de identidade (email-first + fallback contexto)

**Files:**
- Create: `vault/research/identity_resolver.py`
- Test: `tests/research/test_identity_resolver.py`

- [ ] **Step 1: Write failing tests**
Casos:
- e-mail exato -> confidence >=0.90 auto-link
- username parcial -> boost de score
- review_band com empate -> mais fontes, depois recência, depois `conflict:pending`

- [ ] **Step 2: Implement minimal resolver**
- [ ] **Step 3: Run tests**
Run: `pytest tests/research/test_identity_resolver.py -v`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add vault/research/identity_resolver.py tests/research/test_identity_resolver.py
git commit -m "feat(research): implement identity resolver with explicit tie-breakers"
```

### Task 6: Conflito entre fontes e ordem de resolução

**Files:**
- Create: `vault/research/source_priority.py`
- Test: `tests/research/test_conflict_resolution.py`

- [ ] **Step 1: Write failing tests da ordem**
1) prioridade fonte
2) empate -> recência
3) empate total -> pending

- [ ] **Step 2: Implement resolver determinístico**
- [ ] **Step 3: Run tests**
Run: `pytest tests/research/test_conflict_resolution.py -v`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add vault/research/source_priority.py tests/research/test_conflict_resolution.py
git commit -m "feat(research): add deterministic cross-source conflict resolution"
```

### Task 7: Archive guard (3 condições)

**Files:**
- Create: `vault/research/archive_guard.py`
- Test: `tests/research/test_archive_guard.py`

- [ ] **Step 1: Write failing tests**
Só arquiva se:
- >90d sem acesso
- sem referência ativa
- sem conflito pendente

- [ ] **Step 2: Implement guardrail function**
- [ ] **Step 3: Run tests**
Run: `pytest tests/research/test_archive_guard.py -v`
Expected: PASS

- [ ] **Step 4: Commit**
```bash
git add vault/research/archive_guard.py tests/research/test_archive_guard.py
git commit -m "feat(research): add archive guardrails"
```

### Task 8: Pipeline core (11 passos) com modo read-only de self-healing

**Files:**
- Create: `vault/research/pipeline.py`
- Test: `tests/research/test_pipeline_tldv.py`, `tests/research/test_pipeline_github.py`

- [ ] **Step 1: Write failing tests de fluxo TLDV/GitHub**
- [ ] **Step 2: Implementar pipeline core com hooks para:
  - ingest normalizado
  - dedupe
  - context build
  - resolve
  - validate/apply
  - audit logging**
- [ ] **Step 3: Garantir self-healing read-only no MVP**
- [ ] **Step 4: Run tests**
Run: `pytest tests/research/test_pipeline_tldv.py tests/research/test_pipeline_github.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/pipeline.py tests/research/test_pipeline_tldv.py tests/research/test_pipeline_github.py
git commit -m "feat(research): implement v1 pipeline core for tldv and github"
```

### Task 9: Crons de pesquisa + consolidação diária

**Files:**
- Create: `vault/crons/research_tldv_cron.py`
- Create: `vault/crons/research_github_cron.py`
- Create: `vault/crons/research_consolidation_cron.py`
- Modify: `vault/crons/__init__.py`
- Test: `tests/research/test_consolidation_loop.py`

- [ ] **Step 1: Write failing tests para cron entrypoints**
- [ ] **Step 2: Implement cron scripts com env vars de intervalo**
- [ ] **Step 3: Implement consolidator 07h BRT substituindo dream-memory-consolidation**
- [ ] **Step 4: Run tests**
Run: `pytest tests/research/test_consolidation_loop.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/crons/research_tldv_cron.py vault/crons/research_github_cron.py vault/crons/research_consolidation_cron.py vault/crons/__init__.py tests/research/test_consolidation_loop.py
git commit -m "feat(crons): add research tldv/github and daily consolidation cron"
```

### Task 10: Documentação operacional e integração

**Files:**
- Modify: `HEARTBEAT.md`
- Modify: `MEMORY.md`
- Modify: `.gitignore` (se necessário)

- [ ] **Step 1: Atualizar HEARTBEAT com novos jobs e playbook de falha**
- [ ] **Step 2: Atualizar MEMORY com decisão de substituição do dream-memory-consolidation**
- [ ] **Step 3: Verificar política de versionamento dos arquivos state/lock**
- [ ] **Step 4: Commit**
```bash
git add HEARTBEAT.md MEMORY.md .gitignore
git commit -m "docs: update heartbeat/memory for evo research v1 operations"
```

### Task 11: Verificação final de Fase 1

**Files:**
- Test: `tests/research/*.py` + suíte relevante de `vault/tests`

- [ ] **Step 1: Run suite research**
Run: `pytest tests/research -v`
Expected: PASS

- [ ] **Step 2: Run regressão mínima do vault**
Run: `pytest vault/tests/test_identity_resolution.py vault/tests/test_pipeline_module.py vault/tests/test_resilience.py -v`
Expected: PASS

- [ ] **Step 3: Rodar lint/format (se configurado no repo)**
Run: `pytest -q` (fallback)
Expected: PASS geral

- [ ] **Step 4: Commit final de integração**
```bash
git add -A
git commit -m "feat: complete evo wiki research phase 1 implementation"
```

---

## Rollout operacional (pós-merge)

- [ ] Criar/atualizar crons OpenClaw para `research-tldv`, `research-github`, `research-consolidation`
- [ ] Desabilitar cron legado `dream-memory-consolidation`
- [ ] Rodar smoke test manual de cada cron (`run once`)
- [ ] Confirmar escrita em `state/identity-graph/` e ausência de escrita em raw
- [ ] Validar alertas em HEARTBEAT + canal operacional

---

## Risks and Guards

- **Risco:** drift de state
  - **Guard:** SSOT único em `state/identity-graph/state.json`
- **Risco:** concorrência de cron
  - **Guard:** flock + stale lock cleanup
- **Risco:** crescimento de state
  - **Guard:** retenção 180d + compactação mensal
- **Risco:** merge incorreto de identidade
  - **Guard:** self-healing read-only no MVP

---

## Definition of Done (Fase 1)

1. Dois crons ativos (`research-tldv`, `research-github`) processando eventos idempotentes
2. State canônico e identidade persistidos em `state/identity-graph/`
3. Retry/backoff + `pending_retry/exhausted` observáveis
4. Consolidação diária substitui cron legado
5. Testes novos passando + regressão mínima sem quebra
6. Documentação operacional atualizada
