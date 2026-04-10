---
name: memory-vault-design
description: Design para vault Obsidian autônomo inspirado no Karpathy LLM-wiki pattern — memória agêntica de 3 camadas com fact-checking e autonomia total.
status: approved
author: Livy Memory + Lincoln Quinan Junior
created: 2026-04-10
last_updated: 2026-04-10
---

# Design — Memory Vault Autônomo (Karpathy-style)

> **Contexto:** convergência do sistema de memória Living (3 camadas) com o pattern de LLM wiki de Karpathy.
> Prioridades: custo/velocidade, acumulação persistente, integração de fontes externas, autonomia total.
> Arquitetura: vault paralelo em Obsidian-native markdown, 100% autônomo, fact-checkado.

---

## 1. Visão Geral

Criar um `memory/vault/` como **vault Obsidian 100% autônomo**, orientado a entidades e decisões. O agente mantém o vault ativamente — ingere fontes externas, atualiza páginas, detecta contradições e integra conhecimento novo — sem rediscover a cada query.

**Diferença do sistema atual:**
- Hoje: observations são log de ações, topic files são curados manualmente.
- Alvo: vault vivo onde o agente writes & maintains conhecimento persistentemente.

**Garantias:**
- Nunca escreve fora de `memory/vault/`
- Nunca ingere fonte que não seja raw (imutável)
- Toda claim tem confidence score + evidência rastreável

---

## 2. Arquitetura de Camadas

### 2.1 Fronteiras (imutável vs editável)

| Camada | Status | Conteúdo |
|---|---|---|
| **Raw imutável** (source of truth) | nunca editável pelo agente | TLDV API exports, Signal events JSONL, GitHub API, Trello API |
| **Vault editável** | mantido pelo agente | `memory/vault/**/*.md` |
| **Curated legado** | readonly | `memory/curated/*.md` (mantido para compat, não写入) |

**Decisão de fronteira (aprovada):** fontes externas (TLDV/Signal/GitHub/Trello) são raw; observations internas já podem ser retrabalhadas pelo vault.

### 2.2 Estrutura do Vault

```
memory/vault/
├── index.md                      # catálogo navegável (auto-atualizado)
├── log.md                        # timeline append-only de todas as operações
├── AGENTS.md                     # schema: regras de manutenção do vault
│
├── entities/                     # páginas de entidade (projetos, pessoas, sistemas)
│   ├── forge-platform.md
│   ├── bat-conectabot.md
│   ├── delphos-video-vistoria.md
│   ├── tldv-pipeline.md
│   ├── super-memoria-corporativa.md
│   ├── livy-evo.md
│   ├── openclaw-gateway.md
│   └── livy-memory-agent.md
│
├── decisions/                    # decisões com contexto, impacto, status
│   ├── 2026-04-03-whisper-migration.md
│   ├── 2026-04-03-omniroute-upgrade.md
│   ├── 2026-04-03-llm-rerank-moderation.md
│   ├── 2026-04-03-vps-tailscale-network.md
│   ├── 2026-03-31-memory-agent-born.md
│   └── 2026-03-30-tldv-gw-502-workaround.md
│
├── concepts/                     # conceitos recorrentes (linking pages)
│   ├── three-layer-memory-architecture.md
│   ├── progressive-disclosure.md
│   └── omniroute-cascade.md
│
├── evidence/                     # fact-check com fonte oficial
│   ├── omniroute-migration.md
│   ├── telegram-delivery-breakdown.md
│   └── whisper-oom-resolution.md
│
├── lint-reports/                # saídas de lint cycles
│   ├── 2026-04-10-lint.md
│   └── 2026-04-11-lint.md
│
└── .cache/                      # TTL cache de verificações Context7
    └── fact-check/
```

---

## 3. Ciclos Autônomos (Karpathy-style)

### 3.1 Ingest

**Trigger:** novos eventos em raw sources (TLDV decisions, Signal events, GitHub commits, Trello cards).

**Fluxo:**
1. Lê eventos novos do raw source
2. Extrai entidades, claims, decisões
3. Para cada claim: fact-check (Context7 policy)
4. Atualiza 5–15 páginas existentes ou cria novas
5. Mantém backlinks bidirecionais
6. Atualiza `index.md` e `log.md`
7. Emite métricas de observabilidade

### 3.2 Query-as-Write

**Trigger:** resposta a uma pergunta que gera insight novo.

**Fluxo:**
1. Responde pergunta consultando vault
2. Se resposta contém claim nova útil → pergunta: "deseja que eu salve isso no vault?"
3. Se sim → fact-check → cria/atualiza página → log

### 3.3 Lint (manutenção)

**Trigger:** cron periódico (diário ou após N ingests).

**Fluxo:**
1. Detecta contradições (nova claim vs claim existente com fonte mais antiga)
2. Detecta stale claims (alta confiança sem re-verificação > 7 dias)
3. Detecta orphan pages (0 inbound links)
4. Detecta coverage gaps (conceito mencionado mas sem página)
5. Gera `lint-reports/YYYY-MM-DD-lint.md`
6. Corrige automaticamente: orphan links, re-verify stale high-confidence

### 3.4 Repair

**Trigger:** ação corretiva pós-lint ou sinal externo.

**Fluxo:**
1. Resolver contradição: atualizar com fonte mais recente, marcar a antiga como superseded
2. Re-verificar stale claims com Context7
3. Criar página para gap identificado
4. Log da repair action

---

## 4. Fact-Check e Context7 Policy

### 4.1 Níveis de Confiança

| Score | Condição | Uso |
|---|---|---|
| 🟢 **high** | 2+ fontes oficiais independentes ou 1 oficial + 1 corroborada | Decisões, entity facts |
| 🟡 **medium** | 1 fonte oficial OU 2+ sinais indiretos | Contexto, observabilidade |
| 🔴 **low** | 1 sinal indireto ou inferência | Hipóteses, conceito (marcado como draft) |
| ⚫ **unverified** | claim nova sem evidência | Não写入 vault |

### 4.2 Context7 Policy (busca em documentação oficial)

| Situação | Comportamento |
|---|---|
| Claim sobre **OpenClaw** | `read` em `~/.openclaw/docs/` + `openclaw config.get` |
| Claim sobre **Supabase/Postgres** | REST API direto ou schema introspection |
| Claim sobre **API externa** (TLDV, GitHub) | `curl` ou API call para verificar comportamento |
| Claim sobre **infra local** | `exec` para verificar estado real |
| Claim ambígua/low | **Parar** — não escrever até evidência suficiente |

### 4.3 Fluxo Fact-check (automático)

```
Claim extraída → busca fonte oficial → verifica existência → score confiança
→ escreve com citação (frontmatter) → log evidência em .cache/
```

**Budget:** max 3 verificações por ingest cycle para evitar loop infinito.

**Cache:** resultados de Context7 com TTL 24h em `memory/vault/.cache/fact-check/`.

---

## 5. Rastreabilidade e Evidência

### 5.1 Frontmatter de Rastreabilidade

Cada página do vault tem:

```yaml
---
entity: TLDV Pipeline
type: system | decision | concept | evidence
confidence: high | medium | low | unverified
sources:
  - type: official_doc | config | api | signal | observation
    ref: "path ou URL"
    retrieved: YYYY-MM-DD
last_verified: YYYY-MM-DD
verification_log:
  - hash: <sha256 da evidência>
    source: "openclaw config.get pipeline.whisper"
    checked: YYYY-MM-DDTHH:MM:SSZ
last_touched_by: livy-agent
draft: false
---
```

### 5.2 log.md (append-only)

```markdown
## [2026-04-10] ingest | Signal events → entities/tldv-pipeline.md
  claims_added: 3 (1 high, 2 medium)
  evidence_verified: 2
  context7_lookups: 1 (cache hit)

## [2026-04-10] lint | contradiction detected
  entities/tldv-pipeline.md ↔ evidence/omniroute-migration.md
  resolution: updated claim with newer source

## [2026-04-10] query_write | "como está o pipeline TLDV?"
  saved to: concepts/tldv-monitoring-status.md
  confidence: medium
```

Formato prefixado com `## [` para parsing rápido: `grep "^## \[" log.md | tail -5`.

### 5.3 index.md (auto-atualizado)

```markdown
# Vault Index

## Entities (8)
- [[forge-platform]] — Forge platform (Forge) · updated: 2026-04-10
- [[bat-conectabot]] — BAT/ConectaBot observability · updated: 2026-04-08

## Decisions (6)
- [[2026-04-03-whisper-migration]] — Whisper → OmniRoute API · status: resolved
- [[2026-04-03-omniroute-upgrade]] — OmniRoute 3.4.4 → 3.4.9 · status: resolved

## Evidence (3)
- [[omniroute-migration]] — high · last_verified: 2026-04-10
- [[telegram-delivery-breakdown]] — medium · last_verified: 2026-04-09

## Lint Reports
- [[2026-04-10-lint]] — 0 contradictions, 1 orphan fixed
```

---

## 6. Obsidian Client (Privado)

### 6.1 Visão Geral

O vault `memory/vault/` é um **Obsidian vault local**. Não usa cloud, sync público, ou serviço externo.

### 6.2 Acesso Privado

**Opção A — Pasta local (mais simples):**
```
memory/vault/  ←  pasta aberta diretamente no Obsidian (File → Open Vault)
```
- Obsidian detecta `index.md` na raiz e abre como vault
- Obsidian Git plugin permite versionamento local (commits no próprio repo)

**Opção B — Git worktree isolado (mais seguro):**
- `memory/vault/` é um worktree do repo `living/livy-memory-bot` (branch `vault/`)
- `.gitignore` isolado: só versiona `vault/**` + `.gitignore` + `.obsidian/`
- Nenhuma chance de leak — vault é parte do repo privado
- Obsidian abre o worktree como vault

**Recomendado: Opção B** — mantém vault versionado junto com o repo privado `living/livy-memory-bot`, sem exposição a serviços cloud.

### 6.3 Plugins Obsidian Recomendados (todos locales/privados)

| Plugin | Uso | Privacidade |
|---|---|---|
| **Obsidian Git** | auto-commit do vault após mudanças do agente | local only |
| **Dataview** | queries dinâmicas sobre frontmatter (pages por entity, decisões por status) | local |
| **Graph View** | visualizar rede de entidades e links | local |
| **Templater** | template de frontmatter consistente para novas páginas | local |
| **QuickAdd** | criar páginas de decisão com estrutura padronizada | local |
| **Metaedit** | editar frontmatter sem raw markdown | local |

### 6.4 Template de Nova Página (Templater)

```markdown
<%*
const now = new Date().toISOString().slice(0,10);
const type = await tp.system.suggester(["entity", "decision", "concept", "evidence"], ["entity", "decision", "concept", "evidence"]);
-%>
---
entity: <% tp.file.title %>
type: <% type %>
confidence: unverified
sources: []
last_verified: <% now %>
last_touched_by: livy-agent
draft: true
---

# <% tp.file.title %>

## Resumo


## Detalhes


## Fontes

<!-- links para evidências -->


## Histórico
- <% now %> — criado por livy-agent
```

### 6.5 Workflow Observado (Karpathy-style)

1. Agente escreve/mantém vault em background (cron)
2. Usuário abre `memory/vault/` no Obsidian (local)
3. Usuário lê páginas, segue links, consulta graph view
4. Usuário faz perguntas ao agente sobre o que está no vault
5. Agente responde consultando vault + atualiza se necessário

**O vault é o source of truth compartilhado entre agente e humano.**

---

## 7. TDD — Três Suites de Teste

### 7.1 Suite de Testes

```
vault/tests/
├── test_entity_creation.py     # frontmatter correto, path válido, idempotente
├── test_fact_check.py          # score confidence, cache hit/miss, boundary
├── test_lint.py               # contradição, órfãos, stale claims
└── test_index_log.py          # index.md e log.md formatados

scripts/test_vault_seed.py      # seed não quebra estado existente
scripts/test_fact_check.py     # fact-check contra fixtures
scripts/test_lint_cycle.py     # lint com cenários de contradição
scripts/test_security.py       # injeção de paths, escrita fora vault/
```

### 7.2 Fixtures (dados reais, não mock)

```
vault/fixtures/
├── signal_events_sample.jsonl   # 50 eventos reais do Signal
├── topic_files/                  # cópias dos 9 topic files atuais
└── curated_index.md             # snapshot do MEMORY.md
```

### 7.3 Ordem de Implementação

```
test_entity_creation → vault/entity_create.py → ✅
test_fact_check     → vault/fact_check.py    → ✅
test_lint           → vault/lint.py           → ✅
scripts/test_security.py                       → ✅
→ vault/seed.py (QW1+QW3)
→ vault/ingest.py (primeiro ciclo real)
```

---

## 8. Observabilidade

### 8.1 Métricas por Ciclo

| Métrica | Como | Para quê |
|---|---|---|
| `vault_pages_total` | count por tipo (entity/decision/concept/evidence) | growth tracking |
| `vault_claims_total` | count claims por confidence level | quality tracking |
| `lint_contradictions_found` | contradições detectadas por ciclo | health |
| `lint_orphans_found` | páginas sem inbound links | coverage |
| `ingest_claims_added` | claims novas vs re-verificadas | velocity |
| `fact_check_verifications` | chamadas Context7 (hit/miss cache) | custo |
| `fact_check_latency_ms` | tempo por verificação | performance |
| `pipeline_errors` | errors por fase (ingest/lint/fact-check) | reliability |

### 8.2 Dashboard Lightweight

```bash
vault/status.py  # snapshot: pages, claims, health → markdown table
# output: stdout + atualiza HEARTBEAT.md
```

---

## 9. Quick Wins (Semana 1)

| # | Entregável | Esforço |
|---|---|---|
| QW1 | Seed: 8 entity pages extraídas dos topic files atuais | baixo |
| QW2 | `memory/vault/schema/AGENTS.md` com regras de manutenção | baixo |
| QW3 | `vault/seed_index_log.py` → gera `index.md` e `log.md` | baixo |
| QW4 | Primeira evidence page (`evidence/omniroute-migration.md`) | médio |

---

## 10. Riscos e Mitigações

| Risco | Prob. | Impacto | Mitigação |
|---|---|---|---|
| **Fontes oficiais desatualizadas** | alta | médio | executar `openclaw status` e API calls como evidência primária, não só docs |
| **Context7 lookup tokens** | média | baixo | cachear resultados com TTL 24h em `.cache/` |
| **Claim alta confiança mas fonte stale** | baixa | alto | lint inclui re-verify de high-confidence claims > 7d |
| **Loop de re-verificação** | baixa | médio | budget: max 3 verificações por ingest cycle |
| **Orphan pages / vault caos** | média | médio | lint detecta órfãos + cardinalidade por entity (max 20/entity) |
| **Evidência link quebra** (arquivo movido) | baixa | alto | paths relativos + verificar existência antes de escrever |
| **Over-trust em medium confidence** | média | médio | medium só para contexto; decisões usam high only |
| **Write outside vault/** | baixa | crítico | teste `scripts/test_security.py` com paths inject + asserts |

---

## 11. Cronograma Fase 1 (2 semanas)

```
Semana 1 — Fundações
├─ Dia 1-2   vault/ estrutura + schema/AGENTS.md + QW2
├─ Dia 3     TDD suite: entity + fact-check + lint (3 suites)
├─ Dia 4-5   QW1: seed entities + QW3: index/log script
└─ Dia 6-7   QW4: primeira evidence page + lint pass manual

Semana 2 — Autonomia
├─ Dia 8-9   vault/ingest.py (primeiro ciclo real: signal → vault)
├─ Dia 10-11 vault/lint.py (contradictions + orphans + stale)
├─ Dia 12    vault/fact_check.py (Context7 + cache)
└─ Dia 13-14 Full pipeline test → primeiro lint completo → relatório
```

**Critério de saída Fase 1:**
- 8+ entity pages com evidence oficial
- lint pass detecta 0 contradições
- `index.md` e `log.md` atualizam automaticamente
- nenhum dado escrito fora de `memory/vault/`

---

## 12. Decisões Aprovadas

| # | Decisão | Data |
|---|---|---|
| 1 | Vault paralelo (não migrar in-place) | 2026-04-10 |
| 2 | Entidades como estrutura base + decisões como timeline | 2026-04-10 |
| 3 | Raw sources = externas (TLDV/Signal/GitHub/Trello); internals retrabalháveis | 2026-04-10 |
| 4 | Autonomia total no vault (escreve direto, mantém) | 2026-04-10 |
| 5 | Obsidian client via git worktree privado (Opção B) | 2026-04-10 |
| 6 | Context7 policy: oficial docs + API calls > docs estáticos | 2026-04-10 |
| 7 | TDD antes de qualquer produção | 2026-04-10 |
| 8 | Critério de saída: 8 entities, 0 contradições, auto index/log | 2026-04-10 |

---

_Last updated: 2026-04-10 by Livy Memory_
