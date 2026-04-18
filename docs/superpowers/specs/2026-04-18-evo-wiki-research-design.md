# SPEC — Evo Wiki Research: Auto-Research + Wiki Curation System

**Data:** 2026-04-18
**Autor:** Livy Memory (sessão design com Lincoln)
**Status:** Draft — aguardando aprovação

---

## 1. Objetivo

Sistema de pesquisa e curadoria automática onde o **evo opera como motor de pesquisa** — consumindo eventos de TLDV, GitHub e Trello, enriquecendo a wiki v2 (`workspace-livy-memory`) com escrita em camadas curated/operational e bloqueio explícito de raw data sources.

**Escopo:** `workspace-livy-memory` (wiki v2 / livy-memory)

---

## 2. Arquitetura — Orquestração por Crons Especializados

### 2.1 Jobs de pesquisa (trigger: polling via cron)

> **Modelo de trigger v1: polling via cron.** Cada job faz polling na fonte correspondente, detecta eventos novos desde o último checkpoint, e os processa idempotentemente.
>
> **Deduplicação:** cada fonte mantém `last_processed_<source>_id` em arquivo de checkpoint (`.research/<source>/checkpoint.json`). Só eventos com ID > checkpoint são processados.

| Cron | Schedule | Gatilho (polling) | SLA target |
|---|---|---|---|
| `research-tldv` | a definir (provisório: 15min) | summary enriquecida / reunião marcada | latência <30min |
| `research-github` | a definir (provisório: 10min) | PR merged / issue fechada / review | latência <20min |
| `research-trello` | a definir (provisório: 15min) | card criado / movido / concluído | latência <30min |

Cada cron executa o **pipeline interno** (idêntica estrutura, especializado por fonte):

```
1. Checkpoint → lê last_processed_<source>_id
2. Poll       → busca eventos novos desde checkpoint
3. Ingest     → normaliza payload do evento
4. Context    → monta contexto via claude-mem + wiki + FS
5. Resolve    → entity resolution (pessoas/projetos)
6. Hypothesize → gera hipóteses de atualização
7. Validate   → gate de coerência, conflitos, qualidade
8. Apply      → escreve mudanças (apenas paths permitidos)
9. Verify     → tests/lints + log de evidência
10. Checkpoint → atualiza last_processed_<source>_id
```

### 2.2 Boundary de escrita

| Pode alterar | Não pode alterar |
|---|---|
| `wiki v2` (curated/operational) | raw data sources |
| Scripts de ingest/enrich/crosslink | `vault/data/**` |
| Crons | `data/**` |
| Documentação e testes | `exports/**` |
| Playbooks e topic files | `*.jsonl` de ingestão bruta |
| | Dumps (`*.sql`, `*.ndjson`, `*.csv` de origem) |

---

## 3. Identity Graph — Entidades de Pessoa Multi-ID

### 3.1 Modelo canônico de pessoa

```yaml
person_canonical_id: "person:lincoln-quinan-junior"
aliases:
  github: ["lincolnqjunior", "lincoln-living"]
  trello: [{ id: "abc123", username: "lincolnq" }]
  tldv:   [{ name: "Lincoln Quinan Junior", email: "lincoln@..." }]
confidence: 0.85
last_confirmed_at: "2026-04-18T..."
sources: ["tldv:meeting:123", "github:pr:456", "trello:card:789"]
conflicts: []
superseded_by: null
```

### 3.2 Regras de linking (threshold progressivo por fase)

| Fase | Score | Comportamento |
|---|---|---|
| **Fase 1** | `≥ 0.60` | auto-link |
| | `0.45–0.59` | marca como "review_band" — candidato, não aplicado |
| | `< 0.45` | não linka — só registra como candidato |
| **Fase 2+** | `≥ 0.70` | auto-link |
| | `0.50–0.69` | review_band |
| | `< 0.50` | não linka |

**Rationale:** Fase 1 usa threshold baixo (0.60) para maximizar aprendizado. Fase 2 sobe para 0.70 conforme validação.

### 3.3 Self-healing / correção automática

Quando o evo detectar inconsistência:

1. **supersession explícita:** `old_claim → superseded_by → new_claim`
2. **confidence decay:** reduz score do claim antigo
3. **correção de atribuição:** em curated/operational
4. **trilha de auditoria:** timestamp, evidências, root cause da correção

---

## 4. Métricas de Sucesso (Modelo Mix)

### 4.1 Coverage
- `% de entidades com identity canônico resolvido`
- `% de projetos com owner + atribuições + decisões vinculadas`
- `% de eventos que resultaram em atualização útil na wiki`

### 4.2 Recência
- idade média das páginas/topic files críticas
- tempo entre evento detectado → enriquecimento aplicado
- backlog de hipóteses pendentes de validação

### 4.3 Decisões e Correções
- `stale:TODO/pendente → resolvido` (quantidade)
- nº de correções auto-aplicadas (merge/supersession)
- taxa de "correção revertida" (sinal de erro de linking)

---

## 5. Governança e Auditoria

### 5.1 Auditoria por run

Cada execução do cron registra:

```
evento_processado: <event_id>
mudanças_feitas:   [<list>]
evidencias:        [<sources>]
confidence_antes: <float>
confidence_depois: <float>
conflitos:         [<list>]
resolucao:         <strategy>
timestamp:         <ISO>
```

### 5.2 Política de evolução de atribuições

- dedupe progressivo de pessoas multi-ID
- atribuição projeto↔pessoa com confiança incremental
- correção quando evidência nova for superior (recência + suporte multi-fonte)
- **nunca apagar contexto antigo** — sempre via supersession explícita

---

## 6. Rollout em 3 Fases

### Fase 1 — MVP (1-2 semanas)
- ativar 3 crons specialized (research-tldv, research-github, research-trello)
- identity graph mínimo de pessoas
- **threshold auto-link: ≥ 0.60** (Seção 3.2)
- checkpoint + dedupe por event_id em cada fonte
- logs detalhados de todas as ações
- **sem agressividade em delete/merge**

### Fase 2 — Refinamento
- ajuste de thresholds por fonte
- regras de conflito mais fortes
- score de qualidade por mudança
- dashboard de cobertura

### Fase 3 — Auto-tuning
- threshold dinâmico por fonte (baseado em acertos/erros históricos)
- relatórios semanais de confiança e qualidade da wiki
- expansão para mais fontes/eventos

---

## 7. Auto-Correction (Self-Healing)

O evo pode detectar e corrigir:

| Situação | Ação |
|---|---|
| Pessoa duplicada no identity graph | merge + supersession do registro antigo |
| Projeto mal atribuído | re-atribuição com evidência + redução confidence antigo |
| Vínculo fraco contradito por evidência nova | upgrade/downgrade de confidence + nota desupersession |
| Stale entry (>60d sem atualização) | marcar `stale:review` + propor re-validação |
| Conflito de sources | marcar `conflict:pending` + escalar para revisão |

---

## 8. Fluxo Detalhado por Evento

### research-tldv
```
1. receber payload: { meeting_id, summary, topics, decisions, participants }
2. para cada participant → resolver/expandir identity graph
3. extrair topics + decisions → cruzar com MEMORY.md + topic files
4. identificar gaps (topics sem decisão, decisões sem owner)
5. gerar hipóteses de enriquecimento
6. apply se confidence ≥ threshold
7. log + notificar se gap crítico
```

### research-github
```
1. receber payload: { repo, pr_id, author, merged_at, files_changed, review_comments }
2. resolver author → identity graph
3. identificar projetos afetados (por path/arquivo)
4. cruzar decisões relevantes (owners, projetos)
5. aplicar updates (pr merged → atualizar status projeto, decision log)
6. detectar se novo owner/contributor deve ser adicionado
```

### research-trello
```
1. receber payload: { board_id, card_id, action, members, list_name, due_date }
2. resolver members → identity graph
3. identificar projeto ↔ card mapping
4. atualizar projeto com nova atribuição / milestone
5. se card concluded → verificar se decision correspondente existe
```

---

## 9. self-correction — self-healing loop

O evo mantém um loop de revisão contínua:

```
A cada run:
  1. detecta mudanças recentes no identity graph
  2. identifica candidatos a merge (mesma pessoa, IDs diferentes)
  3. identifica candidatos a split (pessoas diferentes, linkadas incorretamente)
  4. para cada candidato → evalua confiança + evidências
  5. se confiança alta o suficiente → apply com supersession
  6. se confiança baixa → marca review_band
  7. log completo de todas as ações de correção
```

---

## 10. Relação com Evo Napkins e Specs Existentes

- **Evo Napkins** são artefatos de decisão — o evo pode consumi-los como contexto e propagar decisions para a wiki
- **Specs existentes** (memória, vault) não são alteradas — este spec adiciona capacidades ao evo sem quebrar workflows atuais
- **HEARTBEAT.md** é atualizado automaticamente pelo evo-research com status dos jobs de pesquisa
- **Consolidation log** registra todas as ações de correção/curadoria feitas pelo evo

---

## 11. Aprovações e Gates

| Tipo | Gate |
|---|---|
| link de pessoa (≥ threshold) | automático |
| merge de identidade | automático com log |
| supersession de claim | automático com auditoria |
| correção de atribuição em projeto | automático com evidência multi-fonte |
| criação de novo topic file | automático com notificação |
| deletion de stale entry | manual (requer aprovação) |

---

_Last updated: 2026-04-18_
