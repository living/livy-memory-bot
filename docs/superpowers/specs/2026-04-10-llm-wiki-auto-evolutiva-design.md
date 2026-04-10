# LLM Wiki — Auto-Evolutiva com Domain Model Living
**Versão:** 1.1 — 2026-04-10  
**Autor:** Livy Memory Agent  
**Status:** Aprovado — aguardando plano de execução

---

## 1. Resumo e Visão

Sistema de wiki persistente que se mantém sozinho: o agente LLM lê fontes brutas, extrai conhecimento, e mantém a wiki atualizada — atualizando entidades, sinalizando contradições, e evoluindo sem intervenção humana contínua. Inspirado no padrão Karpathy (raw sources → wiki → schema), mas com domain model Living como contrato de domínio.

**Ondas de execução:** A → B → C → D (sequenciais puras).

---

## 2. Arquitetura de Alto Nível

```
┌─────────────────────────────────────────────────────────┐
│                    RAW SOURCES (imutáveis)              │
│  TLDV (Supabase)  ·  GitHub API  ·  claude-mem SQLite  │
└────────────────────────┬────────────────────────────────┘
                         │ ingest por fonte
                         ▼
┌─────────────────────────────────────────────────────────┐
│                  WIKI LAYER (LRU compilado)            │
│  decisions/ · entities/ · concepts/                     │
│  Frontmatter = domain model (id_canonical, sources,     │
│  relationships, confidence, lineage)                     │
└────────────────────────┬────────────────────────────────┘
                         │ maintenance
                         ▼
┌─────────────────────────────────────────────────────────┐
│                   SCHEMA LAYER (CLAUDE.md)              │
│  Frontmatter conventions · Ingestion workflow            │
│  Lint rules · Promotion policy · TDD guardrails        │
└─────────────────────────────────────────────────────────┘
```

**Alinhamento com Karpathy:**
- Raw sources = immutable (TLDV, GitHub, claude-mem)
- Wiki = markdown pages owned by LLM
- Schema = CLAUDE.md como "instructions for the LLM agent"
- index.md = catálogo por categoria (entities, concepts, sources)
- log.md = append-only chronological record

---

## 3. Domain Model (Contrato de Domínio Living)

### 3.1 Tipos de Entidade

| Tipo | id_canonical | Requerido | Optional |
|---|---|---|---|
| `Person` | `person:<id>` | id_canonical, source_keys, first_seen_at, last_seen_at | display_name, github_login, email, confidence |
| `Project` | `project:<slug>` | id_canonical, slug, name | status, aliases, confidence |
| `Repo` | `repo:<owner>/<name>` | id_canonical, full_name, owner, name | default_branch, archived, project_ref, source_keys |
| `Meeting` | `meeting:<id>` | id_canonical, source_ref, occurred_at | participants, topics, decisions |
| `Card` | `card:<id>` | id_canonical, source_ref | board_ref, status, assignee |
| `Decision` | `decision:<id>` | id_canonical, statement, sources | confidence, tier, author, status |

### 3.2 Source Record (Contrato Canônico)

```yaml
sources:
  - source_type: signal_event   # ou: github_api, tldv_api, supabase_rest, curated_topic, observation
    source_ref: <url | event-id>
    retrieved_at: 2026-04-10T13:00:00Z
    mapper_version: "signal-ingest-v1"  # obrigatório
```

### 3.3 Relationships

```yaml
relationships:
  - role: author | reviewer | commenter | participant | assignee | decision_maker
    entity_ref: <id_canonical>
    source_ref: <url>
    confidence: high | medium | low
```

### 3.4 Lineage Mínimo Obrigatório

Para toda claim no vault, o lineage mínimo é:

```yaml
lineage:
  run_id: "<uuid>"                        # qual pipeline run gerou
  source_keys: ["tldv:meeting:xxx"]      # IDs das fontes originais
  transformed_at: 2026-04-10T13:00:00Z   # quando foi transformado
  mapper_version: "signal-ingest-v1"       # versão do mapper
  actor: "livy-agent"                     # quem fez a transformação
```

### 3.5 Confidence + Tier Policy

| Confidence | Origem | Tier implícito |
|---|---|---|
| `high` | Official source (github_api, tldv_api com evidência) | A (auto-promote) |
| `medium` | Corroborated (múltiplas fontes) | B (human review) |
| `low` | Indirect (signal único) | B |
| `unverified` | Stub ou conceito novo | C (draft, não promotion-eligible) |

---

## 4. Ondas de Execução

### Onda A — Confiabilidade do Domain Model

**Objetivo:** garantir que o schema de domínio esteja implementado, testado, e migrado.

**Gate de conclusão:** múltiplos tipos de entidade migrados com domain model completo + cross-links + lint 100% green

**Entregas:**

A1. Validators completos em `vault/domain/canonical_types.py` (Person, Project, Repo, Meeting, Card, Decision) — ✅ já existem  
A2. Script de migração: `scripts/elevate_to_domain_model.py` — eleva páginas existentes de frontmatter simples → domain model completo:
   - Adiciona `id_canonical` por tipo
   - Adiciona `source_keys` derivados das sources existentes
   - Adiciona `first_seen_at` / `last_seen_at` derivados do frontmatter
   - Adiciona `relationships` baseados em topic_refs e participantes
   - Idempotente, com backup automático  
A3. **PoC migration:** migrar múltiplos tipos de entidade (TLDV Pipeline + 2 decisões + 1 conceito) com pipeline completo  
A4. Validar: lint 0 errors, quality_review 0 mismatches, cross-links entre entidades  
A5. Testes TDD para migration idempotência + validação de frontmatter  
A6. **Bulk migration:** aplicar a todos os arquivos com dry-run auditado + backup  
A7. Atualizar `vault/index.md` com nova estrutura (entities + decisions + concepts) e `vault/log.md`  

**TDD para Onda A:**
- Testes de validação de frontmatter por tipo de entidade
- Testes de migration idempotência
- Testes de cross-link bidirecional

---

### Onda B — Cobertura de Contexto Histórico

**Objetivo:** seed massivo multi-fonte, processado de fontes antigas → novas.

**Fontes (trilhos paralelos):**

| Fonte | Trilho | Prioridade | Janela |
|---|---|---|---|
| TLDV reuniões | `trilho-tldv` | 1 | Antigas → novas, 30 dias backfill |
| GitHub (issues, PRs, commits) | `trilho-github` | 2 | Commits recentes → antigos |
| claude-mem (observations SQLite) | `trilho-claudemem` | 3 | Últimos 60 dias |

**Ingestion workflow por fonte:**

```
TLDV: meetings (antigas→novas) → summaries.decisions[] → extract decisions
    → reconcile with GitHub (same meeting_id + repo context)
    → upsert to vault/decisions/ (signal_event + tldv_api source types)

GitHub: repos living/* → issues + PRs → extract decisions
    → cross-link with TLDV (same decision statement + window)
    → upsert to vault/decisions/ (github_api source type)

claude-mem: observations → pattern clustering
    → concept pages (observation source type)
    → identity resolution (person mentions → Person entities)
```

**Rastreabilidade balanceada (gate B):**
- Decisões: lineage completo obrigatório (run_id, source_keys, transformed_at, mapper_version, actor)
- Conceitos: lineage parcial aceito na entrada; upgrade para completo em até 24h via cron de enriquecimento

**Reconciliador TLDV↔GitHub:**
- Chave determinística: `decision_hash = sha256(statement + repo_id + meeting_id)`
- Se mesma decisão aparece em TLDV e GitHub: consolidar em uma página com múltiplas sources
- Testes de deduplicação cross-fonte obrigatórios antes de bulk

**TDD para Onda B:**
- Testes de deduplicação cross-fonte
- Testes de ordering antigo→novo (newest wins em contradições)
- Testes de identity resolution (mesma pessoa em fontes diferentes)

---

### Onda C — Observabilidade e Rastreabilidade

**Objetivo:** lineage completo, auditoria, dashboards operacionais.

**Componentes:**

C1. **Run manifest:** cada pipeline run gera `vault/run_manifests/<iso>.jsonl` com:
   - `run_id`, `timestamp`, `sources_processed`, `decisions_written`, `errors`, `gate_overrides`, `mapper_version`, `actor`

C2. **Lineage tracker:** para cada claim na wiki, registra:
   - `source_keys[]` — IDs das fontes originais
   - `transformations[]` — steps de enriquecimento (who changed what when)
   - `promotion_log[]` — história de promoção (draft → confirmed → promoted)

C3. **Contradiction detector:** cron noturno que compara claims novas com existentes; sinaliza:
   - Contradição de data/fato
   - Claim que invalida anterior
   - Gap de contexto novo

C4. **Dashboard operacional:**
   - Métricas: coverage %, stale claims, orphan pages, contradiction queue, lineage completeness %
   - Atualiza `vault/quality-review/` automaticamente

**TDD para Onda C:**
- Testes de run manifest schema validation
- Testes de contradiction detection (com casos de contradição artificiais)
- Testes de lineage trace-back (given claim → follow lineage → reach source)

---

### Onda D — Autoevolução Operacional

**Objetivo:** pipeline que evolui sozinho com feedback loops e policy gates.

**Policy de promoção:**

| Condição | Ação |
|---|---|
| `confidence=high` + `causal_completeness ≥ 0.85` + `≥ 2 fontes` + `tier=A` + sem conflito | **Auto-promote** |
| `confidence=medium` + `tier=B` | Humano aprova (semi-auto) |
| `tier=C` (draft) | Não promotion-eligible até upgrade |

**Feedback loops:**

D1. **Shadow promotion:** candidato promove para shadow queue; cron diário verifica se contradiz algo; se não, auto-promove  
D2. **Human review gate:** reviewer recebe notificação; aprova/rejeita/comenta; rejeição gera reason string  
D3. **False positive tracker:** FP reduz threshold de auto-promotion; se > 2 FP/semana, suspende auto e sobe para humano  
D4. **LLM pre-filter:** LLM analisa claim antes de entrar no vault; rating de confiança; só entra se rating ≥ 0.7  

**Cron jobs operacionais:**

| Cron | Frequência | Ação |
|---|---|---|
| `wiki-enrichment-daily` | 02h BRT | Upgrade concepts para lineage completo |
| `wiki-contradiction-nightly` | 03h BRT | Detecta e sinaliza contradições |
| `wiki-shadow-promotion` | 06h BRT | Tenta auto-promove shadow queue |
| `wiki-human-review-check` | 09h BRT | Verifica pending reviews |
| `wiki-lint-weekly` | Dom 08h | Lint completo + report |

**TDD para Onda D:**
- Testes de policy gate (every combination of conditions)
- Testes de false positive tracker
- Testes de shadow→promoted transition

---

## 5. Data Flow Completo

```
TLDV API (Supabase)
  → meetings (antigas→novas, window=30d)
  → summaries.decisions[]
  → signal_events.jsonl
  → vault.pipeline (ingest)
  → domain model frontmatter (id_canonical, lineage)
  → lint + quality_review
  → vault/decisions/
  → index.md atualizado

GitHub API
  → repos living/*
  → issues + PRs
  → extract decisions (PR titles, issue body, comments)
  → cross-link com TLDV (decision_hash reconciliation)
  → vault/decisions/ (github_api source_type)

claude-mem (SQLite)
  → observations
  → pattern clustering (técnicas, decisões recorrentes)
  → vault/concepts/ (observation source_type)
  → identity resolution (person mentions → Person entities)

Feedback loop
  → vault/feedback-log.jsonl
  → learned-rules.md
  → policy adjustment (threshold, false-positive tracking)
```

---

## 6. Riscos e Mitigações

| Risco | Prob | Impacto | Mitigação |
|---|---|---|---|
| Contradições em cascade ao processar reuniões antigas | Alta | Alto | Processar antigo→novo; newest-wins policy; contradiction detector em C |
| claude-mem observations com PII | Média | Alto | Nunca expor dados de clientes fora de contexto; scrub de e-mails/nomes em B |
| Auto-promotion gera FP em produção | Média | Alto | Shadow queue antes de promote; FP tracker em D; suspende auto se > 2 FP/semana |
| Domain model evolui e quebra backward compat | Baixa | Médio | Versionar mapper_version; compat parsers aceitam ambos schemas; testes de regressão |
| Bulk migration corrompe arquivos | Média | Alto | Backup automático; dry-run obrigatório; diff-and-review antes de aplicar |
| GitHub API rate limit durante seed | Média | Médio | Rate limit-aware fetcher; exponential backoff; cache local |
| Escalação de complexidade: 4 ondas em paralelo | Alta | Médio | Sequencial puro (A→B→C→D); cada onda tem gate de conclusão antes de próxima |
| Vault wiki fica obsoleto sem humans revisando | Média | Médio | Cron de enriquecimento + lint semanal; humanos em loop para Tier B+ |

---

## 7. Quick Wins (antes da Wave A)

Implementáveis no curto prazo enquanto Wave A é definida:

1. **GitHub enriquecimento dos decisions existentes** — adicionar `github_api` source_type aos PRs que já estão no vault
2. **Corrigir index.md** para refletir decisions (24) e concepts (18) reais
3. **Dataview queries** em Obsidian para dashboard básico (coverage %, stale, gaps)
4. **Ativar alias resolution** em `vault/slug_registry.py` para cross-link automático
5. **Script de elevação** de frontmatter existente em `vault/ingest.py` para emitir domain model completo nos novos writes

---

## 8. Definition of Done — Onda A

Wave A concluída **somente** quando todos os itens green:

- [ ] `scripts/elevate_to_domain_model.py` criado com backup automático + idempotência
- [ ] TLDV Pipeline migrada com id_canonical, relationships, source_keys, first_seen_at, last_seen_at
- [ ] 2 decisões migradas com lineage completo (sources + relationships + author + run_id)
- [ ] 1 conceito migrado com lineage completo
- [ ] Cross-links bidirecionais verificados (entidade ←→ decisões)
- [ ] `python3 -m pytest vault/tests/ -q` → 0 failures
- [ ] `domain_lint` → 0 errors
- [ ] `quality_review` → 0 mismatches
- [ ] `vault/index.md` atualizado com nova estrutura de domínio
- [ ] `vault/log.md` registra entrada de migração Wave A
- [ ] Bulk migration aplicada a todos arquivos com backup
- [ ] PR criado com TDD dos novos módulos de validação

---

## 9. Métricas de Sucesso (todas as ondas)

| Métrica | Baseline (2026-04-10) | Target |
|---|---|---|
| domain_lint errors | 0 | 0 |
| quality_review mismatches | 0 | 0 |
| decisions com id_canonical | 0% | ≥ 90% |
| decisions com lineage completo | 0% | ≥ 90% |
| concepts com lineage completo | 0% | ≥ 70% |
| orphan pages | 0 | 0 |
| false positives / semana | 0 | ≤ 2 |
| auto-promotion rate (Tier A) | 0 | ≥ 80% |
| coverage % (fontes processadas) | TBD (audit) | ≥ 85% em D+30 |
