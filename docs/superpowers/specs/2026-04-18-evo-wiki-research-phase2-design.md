# SPEC — Evo Wiki Research Fase 2 (Trello + Self-Healing Write-Mode)

**Data:** 2026-04-18  
**Autor:** Livy Memory (com Lincoln)  
**Status:** Draft — aprovado em sessão para escrita do spec

---

## 1. Objetivo

Evoluir o Evo Wiki Research para Fase 2 com **rollout paralelo em um único PR**, com duas streams:

1. **Stream T (Trello first):** ingestão/pesquisa Trello por polling board↔projeto (cards, list moves, members).  
2. **Stream S (Self-healing depois):** ativar write-mode agressivo com auto-apply + auto-rollback + circuit breaker.

A implementação mantém os guardrails da Fase 1:
- dedupe idempotente por `event_key`
- append-only para correções e rollback
- SSOT em `state/identity-graph/state.json`
- trilha de auditoria e governança operacional

---

## 2. Estratégia de Rollout (B)

A entrega acontece em **um único PR**, mas com gates internos obrigatórios:

```text
Gate T1 (Trello verde) -> Gate S1 (Self-healing verde) -> Gate Final (regressão + docs + operação)
```

### 2.1 Gate T1 — Trello pipeline
- pesquisa por polling board↔projeto
- cards criados/atualizados
- list moves (transições de status)
- members (identity reinforcement)
- testes de unidade e integração verdes

### 2.2 Gate S1 — Self-healing write-mode
- auto-apply com threshold agressivo
- rollback automático append-only
- circuit breaker por fonte
- telemetria para observação do evo

### 2.3 Gate Final
- regressão completa (`tests/research/` + suites críticas do vault)
- documentação operacional (HEARTBEAT/MEMORY/topic file)
- cron `research-trello` registrado e validado

---

## 3. Arquitetura Fase 2

## 3.1 Stream T — Trello

### 3.1.1 Fonte e trigger
- Trigger: **polling por board** (não webhook na Fase 2)
- Intervalo padrão: `RESEARCH_TRELLO_INTERVAL_MIN=20`
- Boards alvo: `TRELLO_BOARD_IDS` + mapeamento board→projeto

### 3.1.2 Eventos suportados
- `trello:card_created`
- `trello:card_updated`
- `trello:list_moved`
- `trello:member_added`
- `trello:member_removed`

### 3.1.3 Chave idempotente
`trello:{event_type}:{card_id}[:{action_id}]`

### 3.1.4 Entidades afetadas
- card → `memory/vault/entities/cards/`
- project (derivado do board mapping)
- person (via member reinforcement)

### 3.1.5 Board ↔ Projeto
Mapeamento explícito versionado em:
`vault/schemas/trello-board-project-map.yaml`

---

## 3.2 Stream S — Self-healing write-mode

### 3.2.1 Política de decisão por confiança
- `>= 0.85` → auto-apply direto
- `0.70–0.84` → auto-apply com log verbose
- `0.45–0.69` → review queue (`pending_review`)
- `< 0.45` → descarta hipótese

### 3.2.2 Rollback automático
Quando regressão é detectada (ex.: conflito reaberto, atribuição revertida por evidência superior):
- append de registro `action: rollback`
- `supersedes: <event_key_original>`
- nunca editar linha antiga
- registrar evidência no `memory/consolidation-log.md`

### 3.2.3 Circuit breaker (por fonte)
- 3 erros consecutivos → pausa auto-apply da fonte
- 5 reverts em 10 ciclos → pausa global de self-healing
- fonte offline >30min → erro operacional (não conta como revert)

---

## 4. SSOT, estado e compatibilidade

- SSOT permanece: `state/identity-graph/state.json`
- `.research/<source>/state.json` continua sendo cache derivado
- incluir `trello` no estado por fonte:
  - `processed_event_keys.trello`
  - `last_seen_at.trello`
  - métricas por fonte em `state_metrics()`

Compatibilidade:
- não quebrar fluxos existentes de `tldv` e `github`
- manter `event_key` backward compatible

---

## 5. Telemetria e observação do evo

Novo arquivo operacional:
`state/identity-graph/self_healing_metrics.json`

Campos mínimos:
- `apply_count_by_source`
- `rollback_count_by_source`
- `review_queue_size`
- `error_streak_by_source`
- `last_breaker_state`

O evo (`evo-analyze` / watchdog) usa esses sinais para:
- alertar regressão de qualidade
- pausar/reabilitar self-healing
- registrar decisões em `experiments.jsonl`

---

## 6. Segurança e guardrails

- append-only para rollback/supersession
- sem escrita em raw data sources
- lock por fonte com `flock` + stale cleanup (TTL 600s)
- retries e backoff seguem política da Fase 1
- conflitos insolúveis continuam como `conflict:pending`

---

## 7. Testes e critérios de aceite

## 7.1 Gate T1 (Trello)
Suites novas esperadas:
- `tests/research/test_trello_client.py`
- `tests/research/test_pipeline_trello.py`
- `tests/research/test_trello_board_project_map.py`

Critério: 100% verde + idempotência validada.

## 7.2 Gate S1 (Self-healing)
Suites novas esperadas:
- `tests/research/test_self_healing_apply.py`
- `tests/research/test_self_healing_rollback.py`
- `tests/research/test_circuit_breaker.py`

Critério: 100% verde + rollback append-only garantido.

## 7.3 Gate Final
- `pytest -q tests/research/`
- `pytest -q vault/tests/test_identity_resolution.py vault/tests/test_resilience.py --ignore=vault/tests/test_reverify_module.py`
- smoke dos crons `research_tldv`, `research_github`, `research_trello`, `research_consolidation`

Critério: sem regressões.

---

## 8. Plano de implementação (resumo)

### Stream T (Trello)
T1. cliente Trello + polling por boards  
T2. normalização e event_key trello  
T3. card upsert + list move status tracking  
T4. member reinforcement  
T5. cron `research_trello` + testes + gate T1

### Stream S (Self-healing)
S1. write-mode agressivo (`>=0.70`)  
S2. rollback append-only  
S3. circuit breaker por fonte  
S4. métricas/telemetria para evo  
S5. integração watchdog + gate S1

### Final
F1. regressão completa  
F2. docs operacionais e memória (STM/LTM/napkin)  
F3. merge do PR único

---

## 9. Variáveis de ambiente

```bash
# Trello
TRELLO_API_KEY=
TRELLO_TOKEN=
TRELLO_BOARD_IDS=
RESEARCH_TRELLO_INTERVAL_MIN=20

# Self-healing
SELF_HEALING_WRITE_ENABLED=true
SELF_HEALING_AGGRESSIVE_MODE=true
SELF_HEALING_BREAKER_ENABLED=true
```

---

## 10. Decisões aprovadas em sessão

- mesmo PR para Trello + self-healing
- rollout paralelo com gates internos (modelo B)
- Trello primeiro, self-healing depois (dentro do mesmo PR)
- self-healing agressivo (`>=0.70`) com rollback automático
- governança sob observação do evo
