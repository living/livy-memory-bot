---
name: memory-vault-agents
description: Schema de manutenção do Memory Vault Autônomo — define como o agente cria, atualiza e mantém páginas do vault.
---

# AGENTS.md — Memory Vault Autônomo

## Visão Geral

Este vault é um **Obsidian wiki mantido 100% pelo agente Livy Memory**. O agente ingere fontes raw, extrai conhecimento, mantém consistência e reporta saúde. O humano lê e consulta — o agente faz todo o trabalho de curadoria.

## Princípios Fundamentais

1. **Nunca escrever fora de `memory/vault/`** — boundary absoluto.
2. **Nunca escrever claim sem evidência** — confidence score mínimo: `medium`.
3. **Decisões exigem `high`** — nenhuma decisão gravada com confidence < high.
4. **Unverified não写入 vault** — claim sem evidência fica em log, não no vault.
5. **Log é append-only** — nunca editar entradas passadas em `log.md`.

## Níveis de Confiança

| Score | Condição | Uso permitido |
|---|---|---|
| `high` | 2+ fontes oficiais independentes OU 1 oficial + 1 corroborada | Entities, decisions, evidence |
| `medium` | 1 fonte oficial OU 2+ sinais indiretos | Context, observabilidade |
| `low` | 1 sinal indireto ou inferência | Conceitos (draft: true) |
| `unverified` | sem evidência | **NÃO写入 vault** — log only |

**Fontes oficiais (para high):**
- `openclaw config.get` / `exec` (estado real do sistema)
- API calls diretas (Supabase, GitHub, TLDV, Trello)
- Docs em `~/.openclaw/docs/`
- Arquivos de topic file curados (`memory/curated/*.md`)

**Fontes aceitas mas não suficientes para high sozinhas:**
- Signal events (alta redundância)
- Observations (parcialmente verificado)
- Chat history

## Context7 Policy — Prioridade de Verificação

Antes de escrever qualquer claim:

1. **`exec` / `openclaw config.get`** — estado real do sistema (prioridade máxima)
2. **API calls diretas** — Supabase REST, GitHub API, TLDV API
3. **Docs oficiais** — `~/.openclaw/docs/**/*.md`
4. **Fixtures locais** — exports e snapshots locais

**Se claim não verificável por nenhuma das acima → `unverified` → não写入 vault.**

**Budget:** max 3 verificações Context7 por ingest cycle (evita loop infinito).

**Cache:** resultados com TTL 24h em `memory/vault/.cache/fact-check/`.

## Ciclo Ingest

1. Lê eventos dos raw sources (signal-events.jsonl, TLDV, GitHub, Trello).
2. Extrai entidades, claims, decisões.
3. Para cada claim: fact-check (Context7 policy).
4. Atualiza 5–15 páginas existentes ou cria novas.
5. Mantém backlinks bidirecionais.
6. Atualiza `index.md` e `log.md`.
7. Emite métricas.

## Ciclo Lint (diário)

1. Detectar **contradições** (nova claim vs claim existente com fonte mais antiga).
2. Detectar **stale claims** (high confidence > 7 dias sem re-verificação).
3. Detectar **orphan pages** (0 inbound links).
4. Detectar **coverage gaps** (conceito mencionado mas sem página dedicada).
5. **Autofix**: orphan links, re-verify stale.
6. Gerar `lint-reports/YYYY-MM-DD-lint.md`.
7. Log → `log.md`.

## Ciclo Query-as-Write

1. Responde pergunta consultando vault.
2. Se resposta contém claim nova útil → perguntar ao humano: "salvar isso no vault?"
3. Se sim → fact-check → cria/atualiza página → log.

## Formato Frontmatter (obrigatório)

```yaml
---
entity: <nome da entidade>
type: entity | decision | concept | evidence
confidence: high | medium | low | unverified
sources: []
last_verified: YYYY-MM-DD
verification_log: []
last_touched_by: livy-agent
draft: false
---
```

**Campos obrigatórios:** `entity`, `type`, `confidence`, `sources`, `last_verified`, `last_touched_by`.

## Formato log.md (append-only)

```markdown
## [YYYY-MM-DD] <tipo> | <descrição>
  <key>: <value>
```

**Tipos de entrada:** `ingest`, `lint`, `query_write`, `repair`, `fact_check`.

**Parsing:** `grep "^## \[" memory/vault/log.md | tail -N` para últimos N eventos.

## Formato index.md

```markdown
# Vault Index

## Entities (<N>)
- [[entity-name]] — <descrição> · updated: YYYY-MM-DD

## Decisions (<N>)
- [[YYYY-MM-DD-decision-title]] — <resumo> · status: <status>

## Evidence (<N>)
- [[evidence-name]] — <confidence> · last_verified: YYYY-MM-DD

## Lint Reports
- [[YYYY-MM-DD-lint]] — <resumo>
```

## Estrutura de Diretórios

```
memory/vault/
├── index.md
├── log.md
├── AGENTS.md                    ← schema
├── entities/                    ← 1 página por entidade
├── decisions/                   ← 1 página por decisão
├── concepts/                   ← conceitos recorrentes
├── evidence/                   ← fact-check com fonte oficial
├── lint-reports/               ← saídas de lint
├── schema/
│   └── AGENTS.md               ← este arquivo
├── .cache/fact-check/          ← TTL cache de verificações
└── fixtures/                   ← fixtures de teste
```

## Regras de Nomeação

- **Entities:** `kebab-case.md` (ex: `tldv-pipeline.md`)
- **Decisions:** `YYYY-MM-DD-slug.md` (ex: `2026-04-03-whisper-migration.md`)
- **Concepts:** `kebab-case.md` (ex: `three-layer-memory-architecture.md`)
- **Evidence:** `kebab-case.md` (ex: `omniroute-migration.md`)
- **Lint reports:** `YYYY-MM-DD-lint.md`

## Backlinks

Toda página deve ter backlinks. Ao criar/atualizar uma página:
1. Adicionar links para páginas relacionadas (`[[page-name]]`).
2. Se link para página que não existe → criar stub com `draft: true`.

## Identity Resolution (Crosslink)

### `github-login-map.yaml`

Arquivo: `memory/vault/schema/github-login-map.yaml`

Objetivo: mapear `login` do GitHub para o **nome canônico de pessoa** usado no vault.

Exemplo:
- `estevesm` → `Esteves`
- `marcioxrocha-living` → `Marcio Rocha`

Sem esse mapa, o pipeline depende apenas de similaridade textual e tende a gerar baixa taxa de match para logins técnicos.

### Fluxo oficial de resolução de identidade

Ordem de resolução (determinística → heurística):

1. **cache** (autor já resolvido em execução anterior)
2. **API** (dados da origem: GitHub/Trello/TLDV)
3. **login-map** (`github-login-map.yaml` / `trello-member-map.yaml`)
4. **frontmatter** (aliases e metadados já gravados nas páginas de pessoa)
5. **fuzzy** (fallback com score conservador)
6. **draft** (se não resolver, criar/usar entidade draft para revisão)

Regra: a primeira resolução válida interrompe a cadeia.

### Bot filtering

Filtro de contas de bot é obrigatório no enriquecimento de PRs e relações:

- ignora autores `*bot*`, `*-bot`, contas de automação e usuários técnicos marcados
- evita auto-referência e poluição das relações `pr-person`
- eventos filtrados não geram edge e devem ser contabilizados em métricas de skip

### Correções do Pipeline Stage 8

Stage 8 (deduplicação/finalização de arestas) deve garantir:

1. dedup determinístico por chave canônica (`source|target|relation|origin`)
2. merge de metadados sem perder proveniência
3. preservação de `confidence` mais alto quando houver conflito
4. escrita idempotente dos arquivos de relacionamento
5. fallback seguro para `draft` quando identidade permanecer ambígua

## Segurança

- **Path traversal:** bloquear `../`, caminhos absolutos, bytes nulos.
- **Script injection:** sanitizar frontmatter (não executar conteúdo markdown).
- **Write boundary:** qualquer write fora de `memory/vault/` → `ValueError`.
- **Fixtures:** fixtures são cópias reais de topic files, mantidas atualizadas.

## Validação Antes de Commit

Antes de qualquer mudança no vault:
1. `test_structure.py` — todas as pastas existem.
2. `test_security.py` — 0 vetores de ataque bloqueados.
3. `test_entity_creation.py` — frontmatter válido.
4. `test_fact_check.py` — confidence scoring correto.
5. `test_lint.py` — 0 contradições (seed) ou contradições reportadas.

## Critério de Saída Fase 1

- 8+ entity pages com evidência oficial.
- lint detecta 0 contradições (no seed).
- `index.md` e `log.md` atualizam automaticamente.
- Nenhuma escrita fora de `memory/vault/`.
- Suite TDD completa passando.

---

_Last updated: 2026-04-12 by Livy Memory_
