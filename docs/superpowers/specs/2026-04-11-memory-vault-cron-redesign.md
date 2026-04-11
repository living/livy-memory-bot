# Memory Vault Cron Redesign — Karpathy Wiki Pattern

> **Spec:** 2026-04-11
> **Status:** Draft
> **Branch:** `master` (post PR #10 merge)
> **Scope:** Memory agent crons only (7 crons → 2 crons + 1 skill)

### Nota sobre código existente

PR #10 mergeou o pipeline `run_external_ingest` para master. As seguintes referências são código já em master:
- `vault/ingest/external_ingest.py` — `run_external_ingest()` (orquestrador de 7 estágios)
- `vault/ingest/card_ingest.py` — `fetch_and_build()` (exportado como `fetch_cards` no orquestrador)
- `vault/enrich_github.py` — `run_enrich_github()` (enriquecimento de PRs)
- `vault/pipeline.py` — `run_signal_pipeline()` com `--reverify --repair`

Phase 1 abaixo estende esse código existente com ingestão incremental, cursors e integração GitHub.

### Sobre o ingest de signal-events

O Phase 1B `vault/ingest.py` (signal-events.jsonl ingest) está contido dentro de `run_signal_pipeline()` e **continua ativo** — processa eventos de signal cross-curation. Não é substituído por este spec. O `vault-ingest` cron adiciona ingestão de fontes externas (TLDV/Trello/GitHub) como camada adicional.

Para localizar cron IDs, rodar `openclaw cron list`.

---

## 1. Propósito e Princípios

**Objetivo:** Transformar o vault de memória em uma wiki viva no padrão Karpathy (llm-wiki) — o LLM mantém, o humano curate via Obsidian.

**3 camadas:**
- **Raw sources** (imutáveis) — TLDV API, Trello API, GitHub API. Nunca modificadas pelo pipeline.
- **Wiki** (LLM mantém) — entities, concepts, decisions, relationships, synthesis em markdown. O pipeline escreve, o humano lê no Obsidian.
- **Schema** — `AGENTS.md` + `MEMORY.md` + este spec definem como o vault é estruturado e operado.

**3 operações:**
1. **Ingest** — adquire de fontes raw, gera/atualiza páginas da wiki
2. **Lint** — health check periódico (contradições, órfãos, stale, gaps)
3. **Query** — pergunta contra a wiki, boas perguntas viram páginas

**Princípios:**
- Raw sources são imutáveis — o pipeline só lê
- Wiki é persistente e compounding — nunca re-derivada do zero
- Simplicidade > completude — 2 crons + 1 skill em vez de 7 crons soltos
- Observabilidade via `index.md` (catálogo) + `log.md` (cronológico) — simples, grep-friendly

---

## 2. Arquitetura de Crônicas + Modos de Operação

### 2.1 `vault-ingest` (3x/dia)

```
Schedule: 0 10,14,20 * * * (America/Sao_Paulo)
Modelo: fastest
Timeout: 300s
Agent: memory-agent
Delivery: announce telegram (accountId: memory, to: 7426291192)
```

**Estágios:**
1. **TLDV** — `run_external_ingest(meeting_days=1)` → meetings, persons, relationships
2. **Trello** — ingestão incremental de todos os boards configurados (cards criados/modificados desde última run)
3. **GitHub** — ingestão incremental de todos os repos configurados (PRs merged/open/recent, issues fechadas recentemente)
4. **Cruzamento** — pessoa X aparece no Trello como membro de cards e no TLDV como participante de meetings → relationship automaticamente
5. **Index** — atualiza `index.md` com catálogo de todas as páginas
6. **Log** — appenda entrada em `log.md` com timestamp, fontes processadas, contadores

**Modos de operação:**
- **Automático (cron):** `meeting_days=1` — só últimas 24h
- **Reunião isolada:** `run_external_ingest(meeting_ids=["id1", "id2"])` — IDs específicos
- **Backfill gradual:** `run_external_ingest(meeting_days=30)` — janela maior, skip meetings que já têm entity no vault (idempotência via `entities/meeting-{id}.md` existe = skip)

**Idempotência:** reprocessar uma reunião não duplica — se entity já existe, overwrite com dados frescos.

**Incremental:** cada run persiste um cursor (timestamp da última run) em `memory/vault/.cursors/{source}.json`. Próxima run só busca a partir dali.

### 2.2 `vault-lint` (1x/dia)

```
Schedule: 0 21 * * * (America/Sao_Paulo)
Modelo: zai/glm-5.1
Timeout: 600s
Agent: memory-agent
Delivery: announce telegram (accountId: memory, to: 7426291192)
```

**Estágios:**
1. **Reverify/Repair** — chamada direta: `run_signal_pipeline(reverify=True, repair=True)`
2. **Contradiction scan** — pages que dizem coisas opostas sobre o mesmo conceito
3. **Orphan scan** — pages sem inbound links do index.md
4. **Stale scan** — pages sem atualização há >30 dias e sem indicação de "arquivado"
5. **Gap scan** — conceitos mencionados em entities mas sem página própria
6. **Cross-reference suggestions** — padrões não conectados ("essa pessoa aparece em 5 meetings mas não tem página de conceito")
7. **Relatório** — gera `lint-reports/{date}.md`
8. **Log** — appenda entrada em `log.md`

### 2.3 Crons removidos

| Cron | ID | Razão |
|---|---|---|
| `openclaw-health` | `63a44a25-...` | Não é memória, é infra |
| `signal-curation` | `53b45f6f-...` | Curadoria genérica sem propósito claro |
| `memory-agent-sonhar` | `9dfe2886-...` | Substituído por vault-ingest |
| `memory-vault-daily-pipeline` | `2ec55149-...` | Mergeado no vault-lint |
| `daily-memory-save` | `b36e4fb9-...` | Wiki já é persistente |
| `memory-agent-feedback-learn` | `aa5cd560-...` | Não tem dados de feedback |
| `autoresearch` | `0c388629-...` | Substituído por vault-lint |

### 2.4 Fontes futuras (não implementar agora)

- **Google Calendar** — agendas de todos os funcionários da Living com consentimento → fonte de pessoas e meetings via Calendar API

---

## 3. Skill `vault-query`

**Nome:** `vault-query`
**Tipo:** Skill global do OpenClaw (disponível para qualquer agente)
**Localização:** `~/.openclaw/skills/vault-query/`

### 3.1 Protocolo de Query

Quando um agente recebe uma pergunta que pode ser respondida pela wiki:

1. **Index first** — lê `index.md` para localizar páginas relevantes
2. **Deep read** — lê as páginas relevantes (entities, concepts, decisions, relationships)
3. **Sintetiza** — compõe resposta com citações (wikilinks `[[page-slug]]`)
4. **Deriva** — se a pergunta gera insight valioso, cria página derivada:
   - `concepts/{slug}.md` — conceito identificado a partir de padrões
   - `decisions/{slug}.md` — decisão extraída de reuniões
   - `synthesis/{slug}.md` — síntese de tema recorrente
5. **Atualiza** — index.md e log.md são atualizados com a nova página

### 3.2 Tipos de pergunta suportados

| Tipo | Exemplo | Páginas consultadas |
|---|---|---|
| Decisão | "O que foi decidido sobre o BAT?" | decisions/*, meeting entities com "BAT" no nome |
| Pessoa | "Quem participou de reuniões com o cliente X?" | person entities, relationships/person-meeting.json |
| Padrão | "Que tópicos aparecem recorrentes nas dailies?" | concepts/*, meeting entities (scan de recorrência) |
| Histórico | "Qual o histórico de decisões do Delphos?" | decisions/* com delphos no slug, meeting entities filtradas |
| Cruzamento | "Que PRs do Forge foram discutidos em reuniões?" | relationships, card entities, meeting entities |
| Status | "O que está acontecendo no projeto X?" | concepts/X, decisions/X, meeting entities recentes |

### 3.3 Manual Operacional (para agentes externos)

Arquivo: `~/.openclaw/skills/vault-query/MANUAL.md`

Conteúdo:
- **Localização do vault:** `memory/vault/`
- **Estrutura de diretórios** (entities, concepts, decisions, synthesis, relationships, lint-reports)
- **Convenções de frontmatter YAML** — campos obrigatórios (entity, type, id_canonical, confidence, sources, source_keys, first_seen_at, last_seen_at)
- **Como ler:** index.md primeiro, depois drill-down nas páginas
- **Como escrever páginas derivadas** — template de frontmatter, como criar wikilinks
- **Como atualizar** — sempre atualizar index.md e log.md ao criar/modificar páginas
- **Schema de entities** — meeting, person, card — campos e tipos
- **Schema de relationships** — formato JSON com edges (from_id, to_id, role, confidence)
- **Limitações** — não modificar raw sources, não deletar pages (marcar como archived)

### 3.4 Arquivos da skill

```
~/.openclaw/skills/vault-query/
├── SKILL.md          # Instruções para agentes OpenClaw (auto-discover)
├── MANUAL.md         # Manual para agentes externos (Claude Code etc.)
└── templates/
    ├── concept.md    # Template de página de conceito
    ├── decision.md   # Template de página de decisão
    └── synthesis.md  # Template de página de síntese
```

---

## 4. Estrutura do Vault (Obsidian-ready)

```
memory/vault/
├── index.md                  # Catálogo de todas as páginas (LLM mantém)
├── log.md                    # Append-only cronológico (grep-friendly)
├── entities/
│   ├── meeting-{id}.md       # Gerado pelo ingest (TLDV)
│   ├── person-{id}.md        # Gerado pelo ingest (TLDV + cruzamento)
│   └── card-{board}-{id}.md  # Gerado pelo ingest (Trello)
├── relationships/
│   └── person-meeting.json   # Edges Person↔Meeting
├── concepts/                 # Criado por query ou lint
├── decisions/                # Criado por query ou lint
├── synthesis/                # Criado por query (insights derivados)
├── lint-reports/             # Gerado pelo lint
└── .cursors/                 # Estado incremental (não versionado, .gitignore)
    ├── tldv.json
    ├── trello.json
    └── github.json
```

**Regras:**
- `entities/`, `relationships/` = gerados pelo pipeline (never edit manually, but can read in Obsidian)
- `concepts/`, `decisions/`, `synthesis/` = podem ser criados pelo pipeline OU manualmente no Obsidian
- `.cursors/` no `.gitignore` — estado operacional, não conhecimento
- `index.md` e `log.md` = mantidos pelo pipeline, legíveis no Obsidian

---

## 5. Migração e Plano de Rollout

### Fase 1 — Setup (imediatamente)
1. Criar skill `vault-query` em `~/.openclaw/skills/vault-query/` (SKILL.md, MANUAL.md, templates)
2. Criar 2 novos crons (`vault-ingest`, `vault-lint`)
3. Integrar `run_enrich_github` no `run_external_ingest` como estágio — import como callable step (não refatorar o código), adicionando após Trello no orquestrador
4. Implementar ingestão incremental com cursors para Trello e GitHub. Formato do cursor: `memory/vault/.cursors/{source}.json` com `{"last_run_at": "ISO8601", "last_run_id": "uuid"}`. Atualizar atomicamente (write tmp + rename) após cada fonte completar com sucesso. Em caso de falha parcial, o cursor NÃO é atualizado — próxima run reprocessa a mesma janela.
5. Implementar atualização automática de `index.md` e `log.md`

### Fase 2 — Desligar crons antigos
6. Desabilitar os 7 crons antigos (um por um, verificando que o novo cobre)
7. Backfill manual gradual: `meeting_days=7` → `30` → `90` → `180`

### Fase 3 — Validação
8. Rodar vault-ingest em dry_run contra dados reais
9. Rodar vault-lint e verificar health do vault
10. Testar vault-query com perguntas reais
11. Abrir vault no Obsidian e verificar navegabilidade

### Critério de sucesso
- Vault responde perguntas que antes precisavam de memória humana
- Obsidian graph view mostra rede conectada de entities/concepts/decisions
- Lint report sem contradições críticas
- Zero crons de memória órfãos
