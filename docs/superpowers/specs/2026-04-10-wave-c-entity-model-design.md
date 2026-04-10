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
| `meeting` | `meeting:{slug}` | `tldv:{meeting_id}` | **nova** |
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

- Integra como estágios feature-flag no `vault.pipeline`
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

## 7. Risco e Mitigação

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| Regressão no resolver de person | média | alto | testes existentes cobrem; add regression suite |
| Duplicação de entidades por idempotência | baixa | médio | testes de dedup obrigatórios em C1 |
| Trello API rate limit | baixa | médio | lookback curto (7d) + throttle |
| Conflito de identidade não tratado | baixa | médio | guardrail REVIEW; monitorar frequência |
| Schema drift em novo ingestor | baixa | baixo | validação canônica em cada upsert |

---

## 8. Histórico de Revisões

| Data | Autor | Mudança |
|---|---|---|
| 2026-04-10 | Livy Memory | Initial draft (brainstormed with Lincoln) |
