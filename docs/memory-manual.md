# Manual de Memória — OpenClaw + claude-mem

> **Versão:** 1.0 — 2026-04-01  
> **Contexto:** Ambiente Living Consultoria (srv1405423, OpenClaw 10.6.3)

---

## Índice

1. [Arquitetura de Memória — Duas Camadas](#1-arquitetura-de-memória--duas-camadas)
2. [Built-in Memory Search](#2-built-in-memory-search)
3. [claude-mem — Observation Memory](#3-claude-mem--observation-memory)
4. [Workflow de 3 Camadas (claude-mem)](#4-workflow-de-3-camadas-claude-mem)
5. [Comparação Direta](#5-comparação-direta)
6. [Guia de Uso Prático](#6-guia-de-uso-prático)
7. [Escrevendo Memórias Eficazes](#7-escrevendo-memórias-eficazes)
8. [Configuração do Worker claude-mem](#8-configuração-do-worker-claude-mem)
9. [Referência Rápida](#9-referência-rápida)

---

## 1. Arquitetura de Memória — Duas Camadas

O ambiente usa **dois sistemas de memória complementares**, cada um com fonte, formato e propósito distintos:

```
┌─────────────────────────────────────────────────────────┐
│  SISTEMA                  FONTE              FORMATO    │
├─────────────────────────────────────────────────────────┤
│  Built-in memory search   Arquivos .md     Trechos     │
│  (openclaw)               no workspace      scored      │
│                                                         │
│  claude-mem               Tool calls        Facts +     │
│  (worker :37777)          observados        narrative   │
└─────────────────────────────────────────────────────────┘
```

**Built-in** → o que foi **escrito**. **claude-mem** → o que foi **feito**.

Ambos são indexados e pesquisáveis. Não são redundantes — são complementares.

---

## 2. Built-in Memory Search

### O que é

Motor de busca semântica nativo do OpenClaw sobre os arquivos `.md` do workspace. Indexa automaticamente via OpenAI `text-embedding-3-small` (ou outro provider configurado).

### Como funciona

```
Query → Embedding → Vector search
      → Tokenize  → BM25 keyword search
      → Weighted merge (70% vector + 30% keyword)
      → Temporal decay (memórias antigas perdem peso)
      → MMR (evita resultados duplicados)
      → Top results com score
```

### Configuração ativa (ambiente Living)

```json5
memorySearch: {
  provider: "openai",          // OpenAI embeddings
  sources: ["memory", "sessions"],
  experimental: { sessionMemory: true },
  query: {
    hybrid: {
      enabled: true,
      vectorWeight: 0.7,
      textWeight: 0.3,
      candidateMultiplier: 4,
      mmr: { enabled: true, lambda: 0.7 },
      temporalDecay: { enabled: true, halfLifeDays: 30 }
    }
  }
}
```

### O que indexa

| Source | Conteúdo | Decay |
|---|---|---|
| `memory/` | Arquivos `.md` — logs diários, notas curadas | ✅ Sim (half-life 30d) |
| `sessions` | Transcrições de sessão (.jsonl) | ✅ Sim |
| Arquivos sem data (MEMORY.md, specs) | Evergreen | ❌ Não |

### Como usar

```bash
# CLI
openclaw memory search "query"

# Dentro do agente — tool automática
openclaw memory search --query "query"
```

### O que retorna

```
memory/forge-platform.md:1-42
Score: 0.684
[Conteúdo do arquivo .md — linhas relevantes]
```

**Score 0.5+** = relevante. Scores menores podem ser ruído.

### Limitações

- Retorna **trechos do arquivo original** — não resume nem interpreta
- Queries muito longas/pipocadas funcionam mal (melhor queries curtas e focadas)
- Não mostra contexto da sessão onde foi escrito
- Só busca em `.md` — não observa tool calls

---

## 3. claude-mem — Observation Memory

### O que é

Plugin que observa **chamadas de ferramenta** feitas pelo agente e as registra como "observations" num worker local (Express.js na porta 37777). Cada observation contém facts, narrative e metadados gerados por um LLM.

### O que observa

O plugin intercepta via OpenClaw event system:
- `before_agent_start` — início de sessão
- `tool_result_persist` — cada tool usada (Read, Write, Exec, etc.)
- `agent_end` — fim de sessão (summary gerado)
- `before_prompt_build` — injeta contexto de observações no system prompt

### Observation types

| Type | Quando | Exemplo |
|---|---|---|
| `🔵 discovery` | Agente descobre algo | "Memory search revela..." |
| `✅ done` | Tool completada com sucesso | "Fixed auth token expiry" |
| `🔴 error` | Erro encontrado | "API returned 500" |
| `🟣 learning` | агент aprende algo novo | "Better approach found" |

### Formato de uma observation

```json
{
  "id": 1721,
  "type": "discovery",
  "title": "Memory search reveals evolution planning infrastructure",
  "subtitle": "Primary session found multiple evolution-related systems...",
  "facts": [
    "Memory search for 'plano evo' returned 15 results...",
    "Design document found at docs/superpowers/specs/...",
    "Evolution Plans Status Inventory exists at ~/.openclaw/workspace-evo/"
  ],
  "narrative": "A memory search in the primary session for 'plano evo' revealed...",
  "concepts": ["how-it-works", "what-changed"],
  "files_read": ["docs/superpowers/specs/2026-03-22-livy-evo-design.md"],
  "files_modified": [],
  "discovery_tokens": 2568,
  "created_at": "2026-04-01T10:59:22.555Z"
}
```

### Observation Feed (SSE → Telegram)

O worker conecta em `GET /stream` e forwards `new_observation` events para o Telegram em tempo real. Útil para monitorar o que o agente está fazendo sem pedir.

**Config no `openclaw.json`:**
```json5
plugins: {
  entries: {
    "claude-mem": {
      enabled: true,
      config: {
        observationFeed: {
          enabled: true,
          channel: "telegram",
          to: "-5158607302",        // chat ID do feed
          accountId: "livy-memory-feed",
          botToken: "..."
        }
      }
    }
  }
}
```

**Nota:** O chat ID `-5158607302` está configurado mas não corresponde aos grupos Living conhecidos. Verificar se é o grupo desejado.

### O que NÃO observa

- Ferramentas com prefixo `memory_` são skipadas (evita recursion)
- Não observa o próprio worker de memória

---

## 4. Workflow de 3 Camadas (claude-mem)

> **Regra:** Nunca buscar full details sem filtrar primeiro. 10x economia de tokens.

O workflow de 3 camadas é obrigatório para uso eficiente do claude-mem:

### Passo 1 — search

Busca o índice e retorna IDs + metadados (~50-100 tokens/result).

```bash
curl "http://localhost:37777/api/search?query=plano+evo&limit=3"
```

Resposta: tabela com ID, hora, tipo, título.

### Passo 2 — timeline

Com o ID mais relevante, busca contexto cronológico ao redor (o que aconteceu antes/depois).

```bash
curl "http://localhost:37777/api/timeline?anchor=1721&depth_before=2&depth_after=2"
```

Retorna as observações vizinhas no tempo — útil para entender o fluxo de trabalho.

### Passo 3 — get_observations

Com IDs filtrados, busca details completos (facts + narrative).

```bash
curl -X POST "http://localhost:37777/api/observations/batch" \
  -H "Content-Type: application/json" \
  -d '{"ids": [1721], "orderBy": "date_desc"}'
```

Retorna o JSON completo com `facts[]`, `narrative`, `files_read[]`, etc.

### Exemplo completo

```bash
# 1. Buscar
curl "http://localhost:37777/api/search?query=forge+platform&limit=3"

# 2. Timeline no mais relevante
curl "http://localhost:37777/api/timeline?anchor=1719&depth_before=1&depth_after=1"

# 3. Full details
curl -X POST "http://localhost:37777/api/observations/batch" \
  -H "Content-Type: application/json" \
  -d '{"ids": [1719]}'
```

---

## 5. Comparação Direta

| Aspecto | Built-in `memory search` | claude-mem |
|---|---|---|
| **O que retorna** | Conteúdo original dos `.md` | Facts + narrative gerados por LLM |
| **Formato** | Trechos com score de relevância | JSON estruturado (facts[], narrative) |
| **Fonte** | Arquivos .md no workspace | Tool calls observados pelo plugin |
| **Melhor para** | Resgatar decisões, specs, contexto histórico | Auditoria de sessões, saber o que foi consumido |
| **Contexto temporal** | Arquivo com data + temporal decay | Timeline nativa por session/observation |
| **System prompt injection** | ❌ Nenhuma | ✅ via `before_prompt_build` hook |
| **Feed em tempo real** | ❌ Não | ✅ SSE → Telegram |
| **Tokens por result** | ~200-500 (trecho) | ~2568 (discovery) / ~500-1000 (observation) |

### Exemplo lado a lado — query "plano evo"

**Built-in:**
```
memory/2026-03-22-evo-design.md (0.511)
[trecho do spec]
```

**claude-mem 3-layer:**
```
facts: ["Design document found at docs/superpowers/specs/...",
        "Evolution Plans Status Inventory exists at ~/.openclaw/workspace-evo/"],
narrative: "A memory search for 'plano evo' revealed a multi-component
            evolution planning system..."
files_read: ["docs/superpowers/specs/2026-03-22-livy-evo-design.md"]
```

### Quando usar qual

| Situação | Built-in | claude-mem |
|---|---|---|
| Resgatar uma decisão técnica | ✅ | ⚠️ |
| Saber se alguém leu um arquivo | ❌ | ✅ |
| Entender o estado de um projeto | ✅ | ⚠️ |
| Auditar o que o agente fez hoje | ❌ | ✅ |
| Buscar por erro específico | ✅ (BM25) | ✅ (FTS5) |
| Contexto injetado no system prompt | ❌ | ✅ |
| Ver fluxo de trabalho de uma sessão | ❌ | ✅ |

---

## 6. Guia de Uso Prático

### Primeiro — configure o ambiente

1. **Verifique se o worker está no ar:**
   ```bash
   curl http://localhost:37777/api/health
   ```
   Deve retornar `{"status":"ok", "version":"10.6.3", ...}`

2. **Verifique o índice built-in:**
   ```bash
   openclaw memory status
   ```
   Debe mostrar `Indexed: X/Y files · Z chunks`

3. **Teste os dois sistemas** com a mesma query para decidir qual usar.

### Para buscar contexto histórico

Use o **built-in** — mais direto, retorna o conteúdo real:

```
openclaw memory search --query "decisão sobre servidor"
```

### Para auditar atividade do agente

Use o **claude-mem** com o workflow de 3 camadas:

```
# Passo 1: buscar
curl "http://localhost:37777/api/search?query=forge&limit=3"

# Passo 2: timeline
curl "http://localhost:37777/api/timeline?anchor=1719&depth_before=1&depth_after=1"

# Passo 3: full details
curl -X POST "http://localhost:37777/api/observations/batch" \
  -H "Content-Type: application/json" \
  -d '{"ids": [1719]}'
```

### Para injetar contexto automaticamente no system prompt

O claude-mem faz isso via `before_prompt_build` hook — não requer ação. Obuilt-in não faz injeção automática.

### Para monitorar o agente em tempo real

Configure o **observation feed** no `openclaw.json` (seção `plugins.entries.claude-mem.config.observationFeed`). Cada tool call gera uma mensagem no Telegram configurado.

### Para saber se um arquivo foi lido pelo agente

**claude-mem** — `files_read[]` no JSON da observation. O built-in mostra o conteúdo, mas não confirma que foi lido.

### Para buscar detalhes técnicos específicos

**Built-in** — BM25 captura IDs, nomes de arquivos, termos técnicos准确. Queries curtas funcionam melhor.

---

## 7. Escrevendo Memórias Eficazes

### Princípio central

> "The files are the source of truth; the model only 'remembers' what gets written to disk."

Arquivos bem escritos = buscas melhores em ambos os sistemas.

### Formato recomendado

```markdown
# Memory — YYYY-MM-DD

## Projeto X

**Status:** ativo | pausado | concluído

**Decisões:**
- Arquitetura: REST API (não GraphQL) — motivo: simplicidade
- Auth: Google OAuth via Supabase — alinhado com Forge

**Pendências:**
- [ ] Migrar auth para Google OAuth

**Bugs conhecidos:**
- #42: JWT expira antes do refresh — root cause em discussão

---

Arquivos evergreen (MEMORY.md, specs, PRDs) são indexados sem temporal decay.
Arquivos com data (`memory/YYYY-MM-DD.md`) decaem — priorize decisões em MEMORY.md.
```

### O que escrever em cada lugar

| Lugar | O que | Exemplo |
|---|---|---|
| `MEMORY.md` | Decisões duradouras, preferências, fatos permanentes | "Lincoln prefere respostas curtas" |
| `memory/YYYY-MM-DD.md` | Log do dia, contexto corrente, tarefas | "Pipeline TLDV parou às 15h" |
| `memory/<projeto>.md` | Contexto de projeto (evergreen) | Stack, deploy, decisões de arquitetura |
| `.claude/napkin.md` | Gotchas, padrões, correções por repo | "ffmpeg compilado do zero — usar binário estático" |

### Erros comuns

- **Escrever demais no daily log** → MEMORY.md fica inchado → busca perde precisão
- **Não actualizar o MEMORY.md** → decisões importantes se perdem no temporal decay
- **Queries muito genéricas** ("bug", "problema", "erro") → muitos resultados, nenhum útil → ser específico
- **Escrever sem contexto** ("deu erro") → inútil para o seu eu futuro → incluir: o que esperava, o que aconteceu, onde

---

## 8. Configuração do Worker claude-mem

### Verificar status

```bash
curl http://localhost:37777/api/health
```

### Endpoints disponíveis

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/health` | Status do worker |
| GET | `/api/search` | Busca indexada |
| GET | `/api/timeline` | Contexto cronológico |
| POST | `/api/observations/batch` | Full details por IDs |
| GET | `/stream` | SSE stream (observation feed) |

### Params de search

```
GET /api/search?query=<q>&limit=<n>&type=<type>&project=<p>&dateStart=<d>&dateEnd=<d>
```

### Params de timeline

```
GET /api/timeline?anchor=<id>&depth_before=<n>&depth_after=<n>&project=<p>
```

### Params de get_observations

```json
POST /api/observations/batch
{ "ids": [123, 456], "orderBy": "date_desc", "project": "openclaw-main" }
```

### Limitações

- Observation feed vai para chat ID configurado — confirmar se é o desejado
- Worker requer `curl localhost:37777` — não funciona se chamadas de rede outbound forem bloqueadas
- observations older than retention policy may be pruned

---

## 9. Referência Rápida

```bash
# ── Built-in ──────────────────────────────────────
openclaw memory status              # estatísticas do índice
openclaw memory search "query"      # busca semântica
openclaw memory index --force       # forçar reindexação

# ── claude-mem worker ──────────────────────────────
curl http://localhost:37777/api/health              # health check
curl "http://localhost:37777/api/search?q=<q>&limit=3"   # passo 1
curl "http://localhost:37777/api/timeline?anchor=<id>&db=1&da=1"  # passo 2
curl -X POST http://localhost:37777/api/observations/batch \
  -H "Content-Type: application/json" \
  -d '{"ids": [<id>]}'                            # passo 3

# ── Definição de prioridade ───────────────────────
Sessão nova após /new ou /reset:
  → openclaw memory search   (built-in, busca conteúdo)
  → curl claude-mem /search  (claude-mem, busca atividade)

Contexto de projeto (specs, decisões):
  → MEMORY.md + memory/<projeto>.md + built-in search

Auditoria (o que foi feito, lido, decidido):
  → claude-mem 3-layer workflow
```

---

## Changelog

| Versão | Data | Mudança |
|---|---|---|
| 1.0 | 2026-04-01 | Versão inicial — descobertas da sessão comparativa |
