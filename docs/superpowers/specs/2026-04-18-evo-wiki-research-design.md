# SPEC — Evo Wiki Research: Auto-Research + Wiki Curation System

**Data:** 2026-04-18
**Autor:** Livy Memory (sessão design com Lincoln)
**Status:** Draft — aguardando aprovação

---

## 1. Objetivo

Sistema de pesquisa e curadoria automática onde o **evo opera como motor de pesquisa** — consumindo eventos de TLDV e GitHub (Trello em Fase 2), enriquecendo a wiki v2 (`workspace-livy-memory`) com escrita em camadas curated/operational e bloqueio explícito de raw data sources.

**Este sistema substitui o `dream-memory-consolidation`.** O research acumula evidências; a cada ciclo, o próprio evo faz dedupe/merge/supersession periódico (Seção 9).

**Escopo:** `workspace-livy-memory` (wiki v2 / livy-memory)

---

## 2. Arquitetura — Orquestração por Crons Especializados

### 2.1 Jobs de pesquisa (trigger: polling via cron)

> **Modelo de trigger v1: polling via cron.** Cada job faz polling na fonte correspondente, detecta eventos novos desde o último checkpoint temporal, e os processa idempotentemente.
>
> **Lock de concorrência:** antes de iniciar, cada job adquire lock exclusivo via `flock(2)` em `.research/<source>/lock`. TTL de 10min (protege contra crash). Se lock não disponível, run é skipado.
>
> **Deduplicação:** o `state/identity-graph/state.json` mantém `processed_event_keys[]` por fonte. Só eventos com `event_key` não existente no state são processados.
>
> **Chave idempotente:** `source:event_type:event_id[:action_id]`.
>
> **Política para eventos tardios/out-of-order:** processa qualquer evento cujo `event_key` ainda não exista no state, mesmo se `event_at < last_seen_at` (janela de tolerância configurável via `RESEARCH_LATE_WINDOW_MIN`).

| Cron | Schedule (env var) | Gatilho (polling) | SLA realístico |
|---|---|---|---|
| `research-tldv` | `RESEARCH_TLDV_INTERVAL_MIN` (default: 15) | summary enriquecida / reunião marcada | latência <1h |
| `research-github` | `RESEARCH_GITHUB_INTERVAL_MIN` (default: 10) | PR merged / issue fechada / review submitted | latência <1h |

> `research-trello` fica para **Fase 2** (Trello tem rate limiting instável e payloads variáveis — prioriza TLDV + GitHub primeiro).

Cada cron executa o **pipeline interno** (idêntica estrutura, especializado por fonte):

```
1. State      → lê last_seen_at + processed_event_keys
2. Poll       → busca eventos novos/alterados desde last_seen_at
3. Ingest     → normaliza payload do evento e calcula event_key
4. Dedupe     → se event_key já processado, skip; senão continua
5. Context    → monta contexto via claude-mem + wiki + FS
6. Resolve    → entity resolution (pessoas/projetos)
7. Hypothesize → gera hipóteses de atualização
8. Validate   → gate de coerência, conflitos, qualidade
9. Apply      → escreve mudanças (apenas paths permitidos)
10. Verify    → tests/lints + log de evidência
11. State     → persiste event_key e avança last_seen_at
```

### 2.2 Boundary de escrita

| Pode alterar | Não pode alterar |
|---|---|
| `wiki v2` (curated/operational) | raw data sources |
| `state/identity-graph/` (identity canônico) | `vault/data/**` |
| Scripts de ingest/enrich/crosslink | `data/**` |
| Crons | `exports/**` |
| Documentação e testes | `*.jsonl` de ingestão bruta |
| Playbooks e topic files | Dumps (`*.sql`, `*.ndjson`, `*.csv` de origem) |
| HEARTBEAT.md, consolidation log | |

### 2.3 Identity Graph — Persistência

**Local:** `state/identity-graph/`

Arquivos:
- `state/identity-graph/people.jsonl` — registry canônico de pessoas (append-only, um registro por linha)
- `state/identity-graph/projects.jsonl` — registry de projetos (append-only)
- `state/identity-graph/state.json` — **única fonte de verdade** para cursores e event_keys processados por fonte

> **Estado único (SSOT):** `.research/<source>/state.json` é cache derivado do `state/identity-graph/state.json`. O `state/identity-graph/state.json` é a fonte canônica. Após cada run, o processo persiste apenas no `state/identity-graph/state.json`. O conteúdo de `.research/<source>/state.json` é reconstruído a partir do state canônico a cada run.

### 2.4 Infraestrutura e Credenciais

**Tokens/APIs:** via env vars em `~/.openclaw/.env` (mesmo padrão dos outros jobs):

```bash
# TLDV
TLDV_API_TOKEN=          # API token do TLDV

# GitHub
GITHUB_PERSONAL_ACCESS_TOKEN=  # token com acesso aos repos Living

# Trello (Fase 2)
TRELLO_API_KEY=
TRELLO_TOKEN=
TRELLO_BOARD_IDS=        # vírgula-separated
```

**Rótulos de credenciais no spec:** `CREDENTIAL: TLDV_API_TOKEN`, `CREDENTIAL: GITHUB_PERSONAL_ACCESS_TOKEN`, etc.

**Credential rotation:** o own de cada provider é responsável por rodar `gh auth refresh` (GitHub) ou atualizar o token no `.env` manualmente. Em Fase 3, avaliar integração com vault de secrets.

### 2.5 Retry e Backoff (API fonte indisponível)

| Situação | Política |
|---|---|
| API retorna 429 (rate limit) | backoff exponencial: 1min → 2min → 4min → 8min (max 3 retries) |
| API retorna 5xx | backoff: 30s → 60s → 120s (max 3 retries) |
| API retorna 403/401 | **não retry** — credencial inválida, escalona erro imediatamente |
| Timeout de rede | retry imediato 1x, depois backoff padrão 5xx |

> Evento que falha após todos os retries fica com `status: pending_retry` no state e é retestado no próximo ciclo do cron.

---

## 3. Identity Graph — Entidades de Pessoa Multi-ID

### 3.1 Modelo canônico de pessoa

```yaml
person_canonical_id: "person:lincoln-quinan-junior"
aliases:
  github: ["lincolnqjunior", "lincoln-living"]
  tldv:   [{ name: "Lincoln Quinan Junior", email: "lincoln@livingnet.com.br" }]
confidence: 0.85
last_confirmed_at: "2026-04-18T..."
sources: ["tldv:meeting:123", "github:pr:456"]
conflicts: []
superseded_by: null
```

### 3.2 Regras de resolução de identidade

**Ordem de resolução (do mais forte ao mais fraco):**

1. **Email exato** (mesmo domínio ou mesmo e-mail canônico) → auto-link imediato (`confidence ≥ 0.90`)
2. **Username parcial** (mesmo username em fontes diferentes, ex: `lincolnq` no Trello + `lincolnq` no GitHub) → candidado forte (`+0.15` boost)
3. **Contexto compartilhado** (mesmos projetos, mesmas reuniões, decisões em comum) → LLM decide com base em evidências cruzadas

**Regras de desempate (review_band tiebreaker):**
- Duas pessoas com score 0.45–0.59 no `review_band`:
  1. Prioriza a que tiver **mais fontes confirmando** o vínculo
  2. Em caso de empate, prioriza a que tiver **evento mais recente** como evidência
  3. Se ainda empatar, marca `conflict:pending` e não linka (requer resolução manual)

### 3.3 Regras de linking (threshold progressivo por fase)

| Fase | Score | Comportamento |
|---|---|---|
| **Fase 1** | `≥ 0.60` | auto-link |
| | `0.45–0.59` | marca como "review_band" — candidato, não aplicado |
| | `< 0.45` | não linka — só registra como candidato |
| **Fase 2+** | `≥ 0.70` | auto-link |
| | `0.50–0.69` | review_band |
| | `< 0.50` | não linka |

**Rationale:** Fase 1 usa threshold baixo para maximizar aprendizado. Fase 2 sobe para 0.70 conforme validação.

### 3.4 Self-healing — Modo read-only no MVP

> **MVP (Fase 1): self-healing roda em modo somente-leitura.** Acumula evidências e gera relatórios de candidatos a merge/supersession, mas **não aplica automaticamente.** Isso evita erro composto: se o merge erra, a próxima iteração usa o registro errado como evidência.

Na **Fase 2**, self-healing ativa com circuit breaker (Seção 3.5).

---

## 4. Métricas de Sucesso (Modelo Mix)

> **Fase 1:** métricas de cobertura e recência apenas. Métricas de qualidade de atribuição ficam para **Fase 2** (precisamos de dados reais antes de definir o que medir).

### 4.1 Coverage
- `% de entidades com identity canônico resolvido`
- `% de projetos com owner + atribuições + decisões vinculadas`
- `% de eventos que resultaram em atualização útil na wiki`

### 4.2 Recência
- idade média das páginas/topic files críticas
- tempo entre evento detectado → enriquecimento aplicado
- backlog de hipóteses pendentes de validação

### 4.3 Decisões e Correções (Fase 2+)
- `stale:TODO/pendente → resolvido` (quantidade)
- nº de correções auto-aplicadas (merge/supersession)
- taxa de "correção revertida" (sinal de erro de linking)

---

## 5. Governança e Auditoria

### 5.1 Auditoria por run

Cada execução do cron registra:

```
evento_processado: <event_key>
mudanças_feitas:   [<list>]
evidencias:        [<sources>]
confidence_antes: <float|N/A>
confidence_depois: <float|N/A>
conflitos:         [<list>]
resolucao:         <strategy>
timestamp:         <ISO>
```

> `confidence_antes/depois` é `N/A` quando o evento não altera linking/atribuição.

### 5.2 Política de evolução de atribuições

- dedupe progressivo de pessoas multi-ID
- atribuição projeto↔pessoa com confiança incremental
- correção quando evidência nova for superior (recência + suporte multi-fonte)
- **nunca apagar contexto antigo** — sempre via supersession explícita

### 5.3 Resolução de conflitos entre fontes

Quando fontes contradictórias afetam o mesmo fato (ex: Trello diz card concluído, mas PR não foi merged), a ordem de resolução é:

1. **Prioridade de fonte:** GitHub > TLDV > Trello (mais authoritative = mais peso na decisão)
2. **Se empate de prioridade:** fonte mais recente wins (`event_at` mais recente)
3. **Se empate total (mesma fonte, mesmo timestamp):** marca `conflict:pending` — não resolve sozinho

**Nunca editar linha antiga para resolver conflito** — sempre append de novo registro superseding com evidência e razão da resolução.

---

## 6. Rollout em 3 Fases

### Fase 1 — MVP (1-2 semanas)
- ativar 2 crons: `research-tldv` + `research-github`
- `research-trello` **deferido para Fase 2**
- identity graph mínimo de pessoas
- **threshold auto-link: ≥ 0.60** (Seção 3.3)
- checkpoint temporal + dedupe idempotente por **event_key**
- **self-healing modo read-only** (não aplica merges — só acumula evidências)
- logs detalhados de todas as ações
- métricas de coverage + recência (Seção 4)
- **sem agressividade em delete/merge automático**

### Fase 2 — Refinamento
- ativar `research-trello`
- self-healing ativa com circuit breaker
- ajuste de thresholds por fonte
- regras de conflito mais fortes
- dashboard de cobertura
- métricas de qualidade de atribuição (Seção 4.3)

### Fase 3 — Auto-tuning
- threshold dinâmico por fonte (baseado em acertos/erros históricos)
- relatórios semanais de confiança e qualidade da wiki
- expansão para mais fontes/eventos
- considerar vault de secrets para credential rotation

---

## 7. Auto-Correction — Circuit Breaker + Rollback

### 7.1 Circuit Breaker (Fase 2+)

Self-healing automático desliga se:
- Taxa de "correção revertida" > 5% nos últimos 50 eventos processados
- `confidence` médio do sistema cair abaixo de 0.50
- 3+ merges aplicados resultaram em `conflict:pending` no mesmo ciclo

**Comportamento quando aberto:** self-healing volta para modo read-only, registra alerta no HEARTBEAT, notifica canal operacional.

### 7.2 Rollback Manual

Se um merge/supersession for aplicado incorretamente:
1. O arquivo `state/identity-graph/people.jsonl` é **append-only** — nunca editar linha existente
2. **Reversão:** append de novo registro com `action: rollback`, `supersedes: <event_key_do_merge_errado>`, `superseded_by: null`
3. O registro errado fica no arquivo mas com `superseded_by` apontando para o rollback
4. **Quem desfaz:** qualquer operador com acesso ao workspace pode criar um registro de rollback (append only)

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

**Critério de gap crítico (v1):**
- decisão sem owner em projeto ativo
- tema recorrente em 3+ reuniões sem decisão
- conflito de identidade de pessoa com impacto em owner/atribuição

**Destino da notificação (v1):**
1. registra no `HEARTBEAT.md` (alerta)
2. envia alerta direto no canal operacional configurado

### research-github

**Escopo v1 (MVP):**
- `pr_merged` ✅ in-scope
- `review_submitted` ✅ in-scope
- `issue_closed` ✅ in-scope

Payload mínimo por tipo:

```yaml
pr_merged:
  event_type: pr_merged
  event_id: <id>
  event_at: <timestamp>
  repo: <repo>
  pr_id: <number>
  author: <login>
  files_changed: []

review_submitted:
  event_type: review_submitted
  event_id: <id>
  event_at: <timestamp>
  repo: <repo>
  pr_id: <number>
  reviewer: <login>
  state: approved|changes_requested|commented

issue_closed:
  event_type: issue_closed
  event_id: <id>
  event_at: <timestamp>
  repo: <repo>
  issue_id: <number>
  closer: <login>
  labels: []
```

Fluxo:
```
1. receber payload normalizado (pr_merged | review_submitted | issue_closed)
2. resolver atores (author/reviewer/closer) → identity graph
3. identificar projetos afetados (por repo/path/labels)
4. cruzar decisões relevantes (owners, projetos, status de execução)
5. aplicar updates de acordo com tipo de evento
6. detectar se novo owner/contributor deve ser adicionado
```

---

## 9. self-correction — Loop de Consolidação (Substitui dream-memory-consolidation)

Este sistema substitui o `dream-memory-consolidation`. A cada ciclo (diário, 07h BRT), o evo executa:

```
A cada consolidação (07h BRT):
  1. ler state/identity-graph/people.jsonl
  2. detectar candidatos a merge (mesma pessoa, IDs diferentes, score ≥ 0.60)
  3. detectar candidatos a split (pessoas linkadas incorretamente)
  4. para cada candidato → avaliar confiança + evidências + taxa de revertida
  5. se self-healing em modo auto (Fase 2+) → apply com supersession
  6. se self-healing em modo read-only (Fase 1) → gera relatório em memory/consolidation-log.md
  7. atualizar HEARTBEAT.md com status do ciclo
  8. archivar entries candidatas: **só arquiva se** todas as condições:
     - sem acesso nos últimos 90d
     - sem referência ativa em decisions/projetos (`sources` sem event_at recente)
     - sem conflito pendente (`conflict:pending == false`)
```

---

## 10. Relação com Evo Napkins e Specs Existentes

- **Evo Napkins** são artefatos de decisão — o evo pode consumi-los como contexto e propagar decisions para a wiki
- **Este spec substitui `dream-memory-consolidation`** — não há mais consolidação separada; o research acumula e a consolidação (Seção 9) faz dedupe/merge/supersession
- **Specs existentes** (memória, vault) não são alteradas — este spec adiciona capacidades ao evo sem quebrar workflows atuais
- **HEARTBEAT.md** é atualizado automaticamente pelo evo-research com status dos jobs de pesquisa

---

## 11. Aprovações e Gates

| Tipo | Gate |
|---|---|
| link de pessoa (≥ threshold) | automático |
| merge de identidade | automático com log (Fase 2+); modo read-only na Fase 1 |
| supersession de claim | automático com auditoria (Fase 2+); modo read-only na Fase 1 |
| correção de atribuição em projeto | automático com evidência multi-fonte |
| criação de novo topic file | automático com notificação |
| deletion de stale entry | manual (requer aprovação) |
| rollback de merge | manual (qualquer operador com acesso) |

---

_Last updated: 2026-04-18_
