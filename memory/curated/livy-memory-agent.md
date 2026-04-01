---
name: livy-memory-agent
description: Agente de memória agêntica da Living Consultoria — mantém contexto institucional de 3 camadas (observations → curated → operational)
type: agent
date: 2026-04-01
project: livy-memory-bot
status: ativo
---

# Livy Memory Agent

## Identidade

- **Bot:** @livy_agentic_memory_bot
- **Grupo Telegram:** `-5158607302`
- **Repo:** `living/livy-memory-bot`
- **Workspace:** `~/.openclaw/workspace-livy-memory/`
- **Timezone:** America/Sao_Paulo (UTC-3)
- **Agent ID real:** `memory-agent` (não `livy-memory` — ver Bug #1781)

## Arquitetura de Memória (3 camadas)

| Camada | Fonte | Path |
|---|---|---|
| 1 — Observations | claude-mem SQLite | `~/.claude-mem/claude-mem.db` |
| 2 — Curated | Topic files | `memory/curated/*.md` |
| 3 — Operational | HEARTBEAT + logs | `HEARTBEAT.md`, `memory/consolidation-log.md` |

## Stack de Memória

| Fonte | Path | Formato |
|---|---|---|
| Observations | `~/.claude-mem/claude-mem.db` | SQLite |
| Topic files | `memory/curated/*.md` | Markdown |
| Índice curado | `MEMORY.md` | Markdown |
| Archive | `memory/.archive/` | Markdown |
| Consolidation log | `memory/consolidation-log.md` | Markdown |

## Scripts de Operação

- `skills/memoria-consolidation/consolidate.py` — Auto Dream adaptado (consolidação)
- `skills/memoria-consolidation/autoresearch_metrics.py` — Métricas de qualidade
- `scripts/autoresearch_cron.py` — Cron de monitoramento (Mente Coletiva)

## Cron Jobs

| Job | Schedule | Descrição |
|---|---|---|
| `dream-memory-consolidation` | 07h BRT daily | Consolidação de stale entries |
| `memory-watchdog` | a cada 4h | Verificação de integridade |
| `autoresearch-hourly` | a cada 1h | Métricas + evolução automática + Mente Coletiva |

## Periodicidade

- Consolidação: 07h BRT (cron `dream-memory-consolidation`)
- Watchdog: a cada 4h (cron `memory-watchdog`)
- HEARTBEAT: a cada 4h
- Autoresearch: a cada 1h (cron `autoresearch-hourly`)

## Repositórios GitHub Associados

- `living/livy-memory-bot` — este workspace
- `living/livy-bat-jobs` — BAT/ConectaBot observability
- `living/livy-delphos-jobs` — Delphos video vistoria
- `living/livy-tldv-jobs` — TLDV pipeline
- `living/livy-forge-platform` — Forge platform

## Credenciais

- Token GitHub: `GITHUB_PERSONAL_ACCESS_TOKEN` em `~/.openclaw/.env`
- claude-mem worker: `127.0.0.1:37777`

## Cross-references

- Infra: [openclaw-gateway.md](openclaw-gateway.md) — gateway que hospeda o agente
- Memória: [claude-mem-observations.md](claude-mem-observations.md) — camada 1 da memória
- Projetos: [forge-platform.md](forge-platform.md), [bat-conectabot-observability.md](bat-conectabot-observability.md), [delphos-video-vistoria.md](delphos-video-vistoria.md), [tldv-pipeline-state.md](tldv-pipeline-state.md)

---

## Status

**ativo** — 2026-04-01

- ✅ Bug #1781 corrigido: agent name era `livy-memory`, deveria ser `memory-agent`
- ✅ Bug #1661 corrigido: accountId `livy-memory-feed` → `memory`; regra channel-per-agent adicionada
- ✅ Feature #1778 integrada: evolução automática via round-robin cursor no autoresearch cron
- ✅ Mente Coletiva (#1727): sistema de consolidação multi-space ativo (memory-agent + Livy Deep)

---

## Decisões

### 2026-03-31 — Sistema de Memória de 3 Camadas

**Decisão:** Criar agente `@livy_agentic_memory_bot` com memória agêntica de 3 camadas.

**MOTIVO:** Decisões técnicas se perdiam entre sessões. A arquitetura em camadas (claude-mem SQLite → topic files → operational) permite que o agente mantenha contexto institucional persistente e que outros agentes consultem memória sem precisar reler tudo.

**Stack:** claude-mem SQLite (observations) → MEMORY.md + topic files (curated) → HEARTBEAT.md (operational)

### 2026-04-01 — Corrigir agent ID de `livy-memory` para `memory-agent` (Bug #1781)

**Decisão:** Todas as delegações para o workspace de memória devem usar `--agent memory-agent`.

**MOTIVO:** O `openclaw agents list` revelou que o agent ID correto é `memory-agent`, não `livy-memory`. Isso causava falha em todas as chamadas de delegação via `run_memory_evolution()`.发现的触发点: observação #1781.

### 2026-04-01 — accountId `livy-memory-feed` → `memory` (Bug #1661)

**Decisão:** Atualizar accountId de `livy-memory-feed` para `memory` no binding JSON.

**MOTIVO:** O accountId antigo estava desatualizado. Corrigido para permitir que o bot funcione corretamente no Telegram.

### 2026-04-01 — Regra: um bot por agente — não compartilhar bot token entre contas (Bug #1661)

**Decisão:** Cada agente deve ter seu próprio canal/Telegram bot token.

**MOTIVO:** Compartilhar bot token entre contas causa erro "Duplicate Telegram bot token". Arquitetura dedicada evita conflito.

### 2026-04-01 — Evolução automática via round-robin cursor (Feature #1778)

**Decisão:** Integrar `run_memory_evolution()` no `autoresearch_cron.py`, processando até 5 arquivos por ciclo com cursor round-robin persistido em `memory/.evolution_cursor`.

**MOTIVO:** O sistema de curadoria manual não acompanhava o volume de arquivos. A evolução automática com cursor round-robin garante que todos os topic files sejam revisados ciclicamente sem overload — cada ciclo processa 5 arquivos, o cursor avança e no próximo ciclo pega os próximos 5.

**Delegação:** cada arquivo é delegado ao agent `memory-agent` com 3-layer research prompt (built-in search → claude-mem API → curated files).

### 2026-04-01 — Mente Coletiva consolidation (Observation #1727)

**Decisão:** Sistema de monitoramento autoresearch usa consolidacao "Mente Coletiva" — múltiplos spaces (memory-agent + Livy Deep) escaneados por phases: Orientation (lê índices) → Gather Signal (detecta stale/orphaned).

**MOTIVO:** Consolidacao centralizada permite visão cross-agent. Lock via PID file (`/tmp/autoresearch.lock`) previne execução concorrente.

---

## Pendências

- [ ] Criar symlink `~/.claude/skills/meetings-tldv` → workspace skills (próximo passo do Bug #1661)
- [ ] Verificar se chat ID `-5158607302` é o grupo desejado para o observation feed SSE
- [ ] Token JWT do TLDV — renovação pendente (impacta pipeline de meetings)

---

## Bugs

### #1781 — agent name errado (`livy-memory` → `memory-agent`) — ✅ CORRIGIDO

**Sintoma:** Todas as delegações via `run_memory_evolution()` falhavam silenciosamente.

**Root cause:** O código usava `--agent livy-memory` mas o agent ID real é `memory-agent`.

**Fix:** Substituir `livy-memory` por `memory-agent` em todas as chamadas de delegação.

### #1661 — accountId desatualizado + regra de canal — ✅ CORRIGIDO

**Sintoma:** Bot não enviava mensagens corretamente.

**Root cause:** accountId `livy-memory-feed` estava obsoleto; compartilhamento de bot token entre agentes causava "Duplicate Telegram bot token".

**Fix:** accountId → `memory`; adicionar regra de channel-per-agent.

---

## Regras Aprendidas

- `add_frontmatter`: +1 (bom trabalho)
- `archive_file`: -1 (não archive ainda)
- `agent_id`: sempre verificar com `openclaw agents list` antes de delegar
- `accountId`: não reutilizar tokens entre contas Telegram

## Notas de Operação

- Topic files nunca expiram — se um projeto está ativo, o topic file permanece
- Decisões técnicas devem ser registradas em `memory/curated/` ao serem tomadas
- HEARTBEAT.md é o dashboard operacional — consultar em cada sessão
- Nunca exponha dados de clientes fora do contexto permitido
