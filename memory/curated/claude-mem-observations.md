---
name: claude-mem-observations
description: Camada de observações agênticas via claude-mem (SQLite) — camada 1 do sistema de memória de 3 camadas. Worker Express.js na porta 37777.
type: memory-layer
date: 2026-04-01
project: claude-mem
status: ativo
---

# claude-mem Observations

## Fonte

- **Path:** `~/.claude-mem/claude-mem.db`
- **Formato:** SQLite
- **Worker:** `127.0.0.1:37777`
- **Health:** `curl http://localhost:37777/api/health`
- **Versão atual:** 10.6.3
- **PID do worker:** 2618
- **Uptime:** ~36h (132587495ms)

## Papel na Arquitetura de Memória

claude-mem é a **camada 1** (observations) do sistema de memória agêntica de 3 camadas:

| Camada | Fonte | Path |
|---|---|---|
| 1 — Observations | claude-mem SQLite | `~/.claude-mem/claude-mem.db` |
| 2 — Curated | Topic files | `memory/curated/*.md` |
| 3 — Operational | HEARTBEAT + logs | `HEARTBEAT.md`, `memory/consolidation-log.md` |

## Endpoints da API

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/health` | Status do worker |
| GET | `/api/search` | Busca indexada (⚠️ ver nota sobre API mismatch) |
| GET | `/api/timeline` | Contexto cronológico |
| POST | `/api/observations/batch` | Full details por IDs |
| GET | `/stream` | SSE stream (observation feed) |

**⚠️ Nota de API:** O plan do AutoResearch TLDV (#1799) assume `/api/search` como endpoint, mas a implementação real usa `/api/observations` com keyword scoring in-memory. Ao integrar com claude-mem, verificar o endpoint real.

## Observation Types

| Type | Quando | Exemplo |
|---|---|---|
| `🔵 discovery` | Agente descobre algo | "Memory search revela..." |
| `✅ done` | Tool completada com sucesso | "Fixed auth token expiry" |
| `🔴 error` | Erro encontrado | "API returned 500" |
| `🟣 learning` | Agente aprende algo novo | "Better approach found" |
| `🔴 bugfix` | Bug corrigido | "Agent ID corrigido" |
| `🟣 feature` | Feature implementada | "Cron job configurado" |

## Estrutura de uma Observation

```json
{
  "id": 1781,
  "type": "bugfix",
  "title": "livy-memory agent name is wrong",
  "subtitle": "openclaw agents list shows the correct agent is memory-agent",
  "facts": ["openclaw agents list shows...", "Fix: change --agent livy-memory..."],
  "narrative": "Discovered that the agent name used in...",
  "concepts": ["gotcha","problem-solution"],
  "files_read": [],
  "files_modified": [],
  "discovery_tokens": 22035,
  "created_at": "2026-04-01T11:52:50.552Z"
}
```

## Workflow de 3 Camadas (claude-mem)

Obrigatório antes de fetchar full details:

1. **search** → retorna IDs + metadados (~50-100 tokens/result)
2. **timeline** → contexto cronológico ao redor do ID relevante
3. **get_observations** → facts + narrative completos

```bash
# Passo 1: buscar
curl "http://localhost:37777/api/search?query=forge&limit=3"

# Passo 2: timeline
curl "http://localhost:37777/api/timeline?anchor=<id>&depth_before=1&depth_after=1"

# Passo 3: full details
curl -X POST "http://localhost:37777/api/observations/batch" \
  -H "Content-Type: application/json" \
  -d '{"ids": [<id>], "orderBy": "date_desc"}'
```

## Two-Source Memory Architecture (para integrations)

O AutoResearch do TLDV usa duas fontes de memória:

| Fonte | Implementação | Via |
|---|---|---|
| OpenClaw built-in | `_openclaw_search()` | CLI: `openclaw memory search --json --max-results` |
| claude-mem | `_claude_mem_search()` | HTTP: `localhost:37777/api/observations` |

**Deduplicação:** Resultados de ambas fontes são mergeados e deduplicados.

## Notas de Operação

- Worker conectado em `127.0.0.1:37777` — **não exposto externamente**
- Observations são a fonte canônica de decisões agênticas
- Observations são destiladas em topic files durante consolidação
- Skills com prefixo `memory_` são skipadas pelo observer (evita recursion)

## Cross-references

- Camada 2: [livy-memory-agent.md](livy-memory-agent.md) — agente que gerencia consolidação das observations
- Infra: [openclaw-gateway.md](openclaw-gateway.md) — gateway que hospeda o plugin claude-mem
- Docs: `/home/lincoln/.openclaw/docs/memory-manual.md` — manual completo da arquitetura

---

## Status

**ativo** — 2026-04-01

- ✅ Worker rodando (PID 2618, v10.6.3, uptime ~36h)
- ✅ API responding correctly
- ✅ Observation feed SSE configurado
- ⚠️ API mismatch: plan do AutoResearch usa `/api/search` mas implementação real usa `/api/observations`

---

## Decisões

### 2026-03-31 — claude-mem como Camada 1 do Sistema de Memória

**Decisão:** Usar claude-mem SQLite como fonte canônica de observações agênticas (camada 1), destiladas em topic files durante consolidação.

**MOTIVO:** Decisões técnicas precisam ser registradas de forma que possam ser consultadas entre sessões. O claude-mem observa tool calls e gera facts+narrative automaticamente, criando um log estruturado que pode ser pesquisado. A curadoria em topic files transforma raw observations em contexto curado e acionável.

### 2026-04-01 — Worker em loopback (não exposto)

**Decisão:** Manter worker claude-mem em `127.0.0.1:37777` sem exposição externa.

**MOTIVO:** O worker contém facts e narrative de todas as sessões. Exposição direta seria um risco de informação. O acesso é feito via CLI/HTTP local — o gateway OpenClaw é o ponto de entrada controlado.

### 2026-04-01 — API mismatch: /api/search vs /api/observations (Bug #1799)

**Decisão:** Ao integrar com claude-mem, usar `/api/observations` com keyword scoring in-memory em vez de `/api/search`.

**MOTIVO:** O plan do AutoResearch TLDV assume `/api/search` como endpoint do claude-mem. Análise do código existente (`insights_generator.py`) revelou que o endpoint real é `/api/observations` com busca sequencial e scoring in-memory. O `/api/search` pode não existir no worker. **Verificar antes de implementar** — usar o padrão confirmado em produção.

---

## Pendências

- [ ] Verificar se endpoint `/api/search` existe no worker claude-mem (observação #1799 indica que não)
- [ ] Corrigir plan do AutoResearch TLDV para usar `/api/observations` em vez de `/api/search`
- [ ] Investigar se observation feed SSE está funcionando corretamente (configuração do `memoryFeed`)

---

## Bugs

### Bug #1799 — API mismatch no plan do AutoResearch

**Sintoma:** Plan de implementação assume `/api/search` como endpoint do claude-mem worker.
**Root cause:** O plan foi escrito antes de verificar a implementação real.
**Status:** Em investigação — implementação real usa `/api/observations`.
**Fix necessário:** Corrigir plan antes de implementar `memory_search.py`.

### Bug histórico — observations skipping "no output"

**Sintoma:** Observações ficavam travadas em "processing" — generator do Claude SDK ignorava chamadas com "no output".
**Root cause:** O sistema disparava `tool_result_persist` mas o SDK pulava observações onde o tool não tinha output.
**Status:** Corrigido — sistema agora processa corretamente.
**Fix:** Observado em 2026-03-30 — não observados detalhes do fix.

---

## Regras Aprendidas

- `claude_mem_api`: verificar endpoints com código real antes de usar em plans
- `claude_mem_loopback`: worker em 127.0.0.1 — não expor
- `observation_workflow`: sempre usar 3-layer workflow (search → timeline → batch) antes de fetchar full details
- `skip_memory_tools`: tools com prefixo `memory_` são skipadas pelo observer
