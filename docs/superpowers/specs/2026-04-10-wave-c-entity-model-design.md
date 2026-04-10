# Wave C — Entity Model Extension: Meeting + Card + Person Identity Strengthen

**Date:** 2026-04-10  
**Status:** Draft → Under Review  
**Author:** Livy Memory Agent (brainstormed with Lincoln)  
**Repo:** `living/livy-memory-bot`  
**Wave:** C (balanceada)  
**Reference:** Karpathy LLM Wiki pattern — https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

---

## Contexto

Wave B entregou identity resolution de `person` via `github_login` e `email`. O vault já tem tipos canônicos para `meeting` e `card` (schema + normalizers), mas sem ingestores ativos.

O objetivo da Wave C é expandir o domínio de entidades navegáveis (quick wins) e usar participação em meetings/cards como sinal de identidade para fortalecer persons — aproximando o grafo de uma visão 360°.

Karpathy LLM Wiki entra como **referência semântica** (estrutura, curadoria, lint) — não como fonte primária de evidência factual.

---

## 1. Modelo de Domínio

### 1.1 Entidades Alvo

| Entidade | ID Canônico | Source Key | Status |
|---|---|---|---|
| `person` | `person:{slug}` | `github:{login}`, `tldv:participant:{id}`, `trello:member:{id}` | existente, reforçada |
| `meeting` | `meeting:{slug}` | `tldv:{meeting_id_source}` | **nova** |
| `card` | `card:{slug}` | `trello:{board_id}:{card_id}` | **nova** |
| `repo` | `repo:{slug}` | `github:{owner}/{name}` | existente |

### 1.2 IdentityResolver Genérico por Tipo

Interface única para todos os tipos:

```python
resolve(type="person",  source_key="tldv:participant:{id}")
resolve(type="meeting", source_key="tldv:{meeting_id}")
resolve(type="card",    source_key="trello:{board_id}:{card_id}")
```

- **person**: estende resolver atual com sinais derivados de meetings/cards (TLDV participants, Trello members).
- **meeting**: lookup por `source_key` exato; sem merge automático.
- **card**: lookup por `source_key` exato; merge automático só se mesmo `board_id:card_id` (idempotência).

### 1.3 Regra de Fortalecimento de Person

Quando meeting/card trouxer vínculo de pessoa:

1. Extrai participant/member e gera `source_key` derivada:
   - meeting participant: `tldv:participant:{meeting_id}:{participant_ref}`
   - card assignee: `trello:assignee:{board_id}:{card_id}:{member_id}`

2. Adiciona sinal em `source_keys` da person canônica (se existir via resolver).

3. Incrementa confiança de forma **conservadora**:
   - teto máximo: `confidence = high` (nunca supera fonte primária)
   - requer ao menos 1 sinal cruzado para ativar incremento

4. **Não faz auto-merge** com base em participação isolada — guardrail mantido.

### 1.4 Papel do Gist Karpathy

- **Referência semântica**: estrutura de camadas (raw → wiki → schema), ciclo Ingest/Query/Lint, arquivo `index.md`, `log.md`
- **Não é fonte factual**: não entra como evidência em decisions, não gera entity pages
- Inspiração aplicada no design de lint e curadoria contínua

---

## 2. Pipeline, Cadência e Guardrails

### 2.1 Pipeline (incremental, sem ruptura)

**Fase C1 — Entidades navegáveis + ingest básico**

- `meeting_ingest.py`: lê TLDV via Supabase (lookback 7 dias); upsert `meeting` por `tldv:{meeting_id}`; extrai participants
- `card_ingest.py`: lê Trello via board/API (lookback por `dateLastActivity`, 7 dias); upsert `card` por `trello:{board_id}:{card_id}`; extrai assignees
- Ingest é idempotente (repetir não duplica)

**Fase C2 — Relationship graph + fortalecimento de person**

- Gera edges:
  - `person -> meeting` com role `participant` (default) ou `decision_maker` (se campo `is_decision_maker`)
  - `person -> card` com role `assignee` (se assignee) ou `participant` (se member sem assignee)
- Passo de fortalecimento: adiciona `source_keys` derivadas em person + incremento conservador de confiança

**Fase C3 — Operação, lint e curadoria contínua**

- Integra como estágios feature-flag no `vault.pipeline` (flags sugeridas: `WAVE_C_C1_ENABLED`, `WAVE_C_C2_ENABLED`, `WAVE_C_C3_ENABLED`; defaults: C1=true, C2=false, C3=false)
- Relatório de qualidade: meetings/cards ingeridos, persons fortalecidas, conflitos de identidade
- Lint/repair: órfãos, role inválida, falta de lineage/source_mapper, schema drift

### 2.2 Cadência

| Estágio | Frequência | Justificativa |
|---|---|---|
| meetings ingest | a cada 2h | volátil, decisões do dia |
| cards ingest | a cada 2h | volátil, status muda rápido |
| identity strengthen + lint | 1x/dia (07h BRT) | custo/benefício |

### 2.3 Guardrails

1. **Sem auto-merge de person com sinal único** — participações são evidência, não prova de identidade
2. **Merge automático só com ≥2 source_keys + match forte** — mantêm barreira atual
3. **Conflito** (`same source_key → 2 canonical_ids`) vai para fila REVIEW
4. **Role taxonomy** segue contrato atual (sem `part_of`)
5. **Idempotência** — reprocessar lote não duplica entidades/edges
6. **Feature-flag por estágio** — C1 pode rodar antes de C2 sem quebra
7. **Idempotência do strengthen** — `source_keys` derivadas são deduplicadas e incremento de confiança é idempotente (re-run não acumula acima do teto)

---

## 3. Entrega em Fases Curtas

### Fase C1 — Entidades navegáveis (quick win imediato)

**Entregáveis:**
- `vault/ingest/meeting_ingest.py` — TLDV/Supabase → `meeting` entities
- `vault/ingest/card_ingest.py` — Trello API/board → `card` entities
- `vault/tests/test_meeting_ingest.py` — parsing timestamps, dedup, schema validation
- `vault/tests/test_card_ingest.py` — dedup, idempotência, schema validation

**Critério de aceite C1:**
- [ ] given a TLDV meeting with participants → creates `meeting` entity + edges
- [ ] given a Trello card with board+assignee → creates `card` entity with `trello:{board}:{card}`
- [ ] reprocessar mesmo lote não duplica entidades (idempotência)

### Fase C2 — Relationship graph + person strengthening

**Entregáveis:**
- `vault/domain/identity_resolution.py` refatorado com resolver genérico
- Edges `person -> meeting` e `person -> card` via `relationship_builder`
- Passo de fortalecimento de person (source_keys + confiança conservadora)
- `vault/tests/test_identity_strengthen.py` — guardrails, sem auto-merge indevido

**Critério de aceite C2:**
- [ ] given a person with matching github_login → identity resolved correctly
- [ ] given participation signal from meeting → `source_key` added to person, confidence incremented conservatively
- [ ] given conflict of identity → goes to REVIEW, not auto-merge
- [ ] reprocessar não regredir resolver atual de person

### Fase C3 — Operação, lint e curadoria contínua

**Entregáveis:**
- Integração feature-flag no `vault.pipeline`
- Métricas de qualidade: entities ingested, persons strengthened, conflicts
- Lint estendido: orphan links, invalid roles, missing lineage, schema drift
- `vault/tests/test_wave_c_integration.py` — pipeline E2E

**Critério de aceite C3:**
- [ ] `vault.pipeline` executa C1+C2 sem regressão crítica
- [ ] lint sem gaps/orphans/stale críticos
- [ ] navegação por IDs e backlinks funcional no vault
- [ ] Karpathy pattern aplicado no design de lint e curadoria

---

## 4. Definições e Terminologia

| Termo | Definição |
|---|---|
| `source_key` | Identificador opaco de origem: `{provider}:{ref}` |
| `meeting_id_source` | Campo canônico da entidade meeting (espelha `meeting_id` do TLDV) |
| `id_canonical` | Identificador estável do vault: `{entity_type}:{slug}` |
| `identity resolve` | Encontrar/mergear entidades por `source_key` ou sinais cruzados |
| `strengthen` | Adicionar `source_keys` derivados + incrementar confiança de person |
| `lookback` | Janela temporal retroativa para ingest (dias) |
| REVIEW | Estado de conflito que requer curadoria humana |
| feature-flag | Flag que permite ativar/desativar estágio sem quebra |

---

## 5. Dependências e Pré-condições

- Supabase TLDV acessível (tabelas `meetings`, `summaries`, `participants`)
- Trello API com token + board_id configurado
- `vault/domain/canonical_types.py` — tipos já validados (person, meeting, card, repo, decision)
- `vault/domain/normalize.py` — normalizers existentes (não mexer no contrato)
- `vault/domain/relationship_builder.py` — roles permitidos (mantidos)
- HEARTBEAT.md atualizado com novos jobs após deploy

---

## 6. Out of Scope (Wave C)

- calendar_event (Google Calendar) — reservado para extensão futura
- Google Drive / Gmail / WhatsApp — Super Memória Corp (Robert, escopo diferente)
- Ingest de decisions via meetings (já existe pipeline separado)
- Alteração de schema de entities/decisions já existentes (backward compat)

---

## 7. Observabilidade

### 7.1 Métricas Operacionais (emittidas a cada run)

| Métrica | Tipo | Descrição |
|---|---|---|
| `wave_c.ingest.meetings.total` | counter | meetings lidos do TLDV por run |
| `wave_c.ingest.meetings.created` | counter | meetings criados (upsert new) |
| `wave_c.ingest.meetings.updated` | counter | meetings atualizados |
| `wave_c.ingest.cards.total` | counter | cards lidos do Trello por run |
| `wave_c.ingest.cards.created` | counter | cards criados |
| `wave_c.ingest.cards.updated` | counter | cards atualizados |
| `wave_c.edges.person_meeting.created` | counter | edges `person→meeting` gerados |
| `wave_c.edges.person_card.created` | counter | edges `person→card` gerados |
| `wave_c.strengthen.persons.updated` | counter | persons fortalecidas |
| `wave_c.strengthen.source_keys.added` | counter | source_keys derivadas adicionadas |
| `wave_c.conflict.review.total` | counter | conflitos enviados para REVIEW |
| `wave_c.error.ingest.total` | counter | erros no ingest (por source: tldv, trello) |
| `wave_c.run.duration_ms` | histogram | duração total do run |

### 7.2 Logs de Auditoria (append-only)

Cada run emite um evento estruturado em `memory/vault/wave-c-runs/{run_id}.json`:

```json
{
  "run_id": "wc-2026-04-10T14:30:00Z",
  "phase": "C1",
  "started_at": "2026-04-10T14:30:00Z",
  "ended_at": "2026-04-10T14:31:23Z",
  "duration_ms": 83200,
  "source": "tldv|trello",
  "lookback_days": 7,
  "results": {
    "meetings_ingested": 12,
    "meetings_created": 4,
    "meetings_updated": 8,
    "cards_ingested": 38,
    "cards_created": 11,
    "cards_updated": 27,
    "errors": [],
    "skipped": []
  },
  "quality": {
    "validation_errors": 0,
    "dedup_skipped": 5,
    "review_queue": 0
  }
}
```

### 7.3 Alertas

| Trigger | Severidade | Ação |
|---|---|---|
| `error.ingest` > 0 por 3 runs consecutivos | 🔴 CRÍTICO | pausar ingest + notificar canal `memory` |
| `conflict.review.total` growing > 10/ dia | 🟡 WARN | agendar curadoria manual |
| run duration > 5min sem feature-flag | 🟡 WARN | investigar source API latência |
| `wave_c.strengthen.persons.updated` = 0 por 7 dias | ⚠️ INFO | pode indicar ausência de meetings/cards novos |

---

## 8. Rastreabilidade (Lineage)

### 8.1 Campos de Lineage por Estágio

Todo entity/edge escrito pelo Wave C carrega lineage completo:

```yaml
# Exemplo: meeting entity
id_canonical: "meeting:2026-04-10-daily-status"
meeting_id_source: "daily-2026-04-10"
source_keys:
  - "tldv:daily-2026-04-10"
  - "mapper:wave-c-meeting-ingest-v1"
first_seen_at: "2026-04-10T14:30:00Z"
last_seen_at: "2026-04-10T14:30:00Z"
confidence: "medium"
lineage:
  run_id: "wc-2026-04-10T14:30:00Z"
  phase: "C1"
  source: "tldv"
  lookback_days: 7
  mapper_version: "wave-c-meeting-ingest-v1"
  actor: "livy-agent"
  transformed_at: "2026-04-10T14:30:00Z"
```

```yaml
# Exemplo: edge person→meeting
from_id: "person:robert-silva"
to_id: "meeting:daily-2026-04-10"
role: "participant"
from_source_key: "github:robert-silva"
to_source_key: "tldv:daily-2026-04-10"
confidence: "high"
lineage:
  run_id: "wc-2026-04-10T14:30:00Z"
  phase: "C2"
  mapper_version: "wave-c-relationship-builder-v1"
  actor: "livy-agent"
  transformed_at: "2026-04-10T14:31:00Z"
```

### 8.2 Rastreamento de Run

- `run_id` = ISO timestamp do início do run (UTC)
- Permite cross-reference entre: logs de run, entidades escritas, métricas, e events no `claude-mem`
- Run files em `memory/vault/wave-c-runs/` funcionam como audit log imutável

---

## 9. Resiliência

### 9.1 Tratamento de Erros por Camada

| Camada | Estratégia | Comportamento em Falha |
|---|---|---|
| **TLDV/Supabase fetch** | retry exponencial com jitter (max 3) | loga erro, continua com dados disponíveis |
| **Trello API fetch** | retry exponencial com jitter (max 3) + rate limit backoff | loga erro, continua com dados disponíveis |
| **Upsert entity** | validação pré-upsert (schema canônico) | entidade rejeitada com erro; run continua |
| **Edge creation** | validação de role + from/to existence | edge rejeitado; entidade pai não afetada |
| **Strengthen pass** | idempotência por source_key | re-run não duplica nem estaca |
| **Pipeline global** | feature-flag por estágio | estágio com erro é desabilitado automaticamente após 3 failures |

### 9.2 Circuit Breaker

```
Se Trello API retornar 429 ou 5xx por 2 runs consecutivos:
  → desabilitar card ingest (WAVE_C_C1_CARD_ENABLED=false)
  → alertar canal memory
  → re-habilitar automaticamente após 1h ou manual
```

### 9.3 Dead Letter (Conflitos e Rejeições)

Conflitos de identidade e validações rejeitadas são serializados em:

```
memory/vault/wave-c-runs/{run_id}.review-queue.jsonl
```

Formato:
```json
{"type": "identity_conflict", "source_key": "github:robert-silva", "candidates": [...], "run_id": "wc-...", "created_at": "..."}
{"type": "validation_error", "entity": {...}, "errors": [...], "run_id": "wc-...", "created_at": "..."}
```

Revisão manual consume entries deste arquivo; entrada removida após resolução.

### 9.4 Backfill e Reconciliation

- **Backfill manual**: `python3 -m vault.pipeline --backfill wave-c --phase C1 --days 30`
- Reconcile roda junto com consolidation (07h BRT): detecta entities sem `mapper_version` da Wave C e tenta recompletar lineage
- Backfill respeita idempotência (não sobrescreve `last_seen_at`.backward)

---

## 10. Fact-Checking e Qualidade de Dados

### 10.1 Validações na Ingesta (pré-upsert)

| Check | Regra | Ação em Falha |
|---|---|---|
| `meeting_id` não vazio | string não vazio | reject entity |
| `card_id` não vazio | string não vazio | reject entity |
| `board_id` presente em card | string não vazio | reject entity |
| `started_at` formato ISO | datetime parse | skip row, log warning |
| `dateLastActivity` formato ISO | datetime parse | skip row, log warning |
| Entity schema canônico | `validate_meeting()` / `validate_card()` | reject + emit validation_error |

### 10.2 Consistência Cruzada (pós-upsert)

| Check | Regra | Ação em Falha |
|---|---|---|
| Participant referenciável | person entity existe ou foi criada no mesmo run | cria person stub com `confidence=low` |
| Assignee referenciável | person entity existe ou foi criada no mesmo run | cria person stub com `confidence=low` |
| No duplicate source_key | source_key único por `id_canonical` | rejeita duplicata, log warning |
| Edge consistency | `from_id` e `to_id` existem | não cria edge, log warning |
| Role válido | role em `RELATIONSHIP_ROLES` | rejeita edge |

### 10.3 Monitoramento de Qualidade Contínua

- **Lint do vault** (daily): rodado junto com consolidation — detecta orphan edges, stale entities, missing lineage
- **Métrica de cobertura**: `entities com lineage.run_id wave-c` / `total entities` — target ≥ 90% em 7 dias
- **Drift detection**: se `mapper_version` da Wave C отсутствует em >10% das entidades de meeting/card num período de 7 dias, alertas de health check disparam

---

## 11. Risco e Mitigação (Expandido)

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Regressão no resolver de person | média | alto | regression suite em C2; rodar suite completo antes de merge |
| Duplicação de entidades por idempotência | baixa | médio | testes de dedup obrigatórios em C1 + idempotency check no lint |
| Trello API rate limit | baixa | médio | backoff exponencial + circuit breaker; lookback curto (7d) |
| Trello API 5xx / outage | baixa | alto | circuit breaker; alerta crítico se 3 failures consecutivos |
| Supabase/TLDV API outage | baixa | alto | alerta crítico; run marcado como incompleto; não писать entidades parciais |
| Conflito de identidade não tratado | baixa | médio | REVIEW queue + alerta se > 10 conflitos/dia |
| Schema drift em novo ingestor | baixa | baixo | validação canônica em cada upsert + lint daily |
| Dados obsoletos em person stub | baixa | médio | Reconciliation daily move stubs para REVIEW se sem sinais há 30d |
| Fork de person entities por múltiplos sources | média | médio | guardrail ≥2 source_keys para auto-merge + lint de duplicatas |
| Feature-flag em estado inconsistente entre runs | baixa | médio | flags lidas do config no início do run; jamais mutate in-flight |
| Backfill sobrescreve dados legítimos | baixa | alto | idempotência por `last_seen_at`; re-run não reduz `confidence` |
| Auditoria de run corrompida (disk full) | baixa | médio | atomic write: escrever em .tmp e renomear ao final |

---

## 12. Histórico de Revisões

| Data | Autor | Mudança |
|---|---|---|
| 2026-04-10 | Livy Memory | Initial draft (brainstormed with Lincoln) |
| 2026-04-10 | Livy Memory | Expandido com §7 observabilidade, §8 rastreabilidade, §9 resiliência, §10 fact-checking, §11 riscos expandido |
