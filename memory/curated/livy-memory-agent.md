---
name: livy-memory-agent
description: Agente de memória agêntica da Living Consultoria — mantém contexto institucional de 3 camadas
type: agent
date: 2026-03-31
project: livy-memory-bot
status: ativo
decision: Sistema de memória de 3 camadas ativo — observations (SQLite) → curated (topic files) → operational (HEARTBEAT)
---

# Livy Memory Agent

## Identidade

- **Bot:** @livy_agentic_memory_bot
- **Grupo Telegram:** `-5158607302`
- **Repo:** `living/livy-memory-bot`
- **Workspace:** `~/.openclaw/workspace-livy-memory/`
- **Timezone:** America/Sao_Paulo (UTC-3)

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

## Cron Jobs

| Job | Schedule | Descrição |
|---|---|---|
| `dream-memory-consolidation` | 07h BRT daily | Consolidação de stale entries |
| `memory-watchdog` | a cada 4h | Verificação de integridade |
| `autoresearch-hourly` | a cada 1h | Métricas + melhoria automática |

## Periodicidade

- Consolidação: 07h BRT (cron `dream-memory-consolidation`)
- Watchdog: a cada 4h (cron `memory-watchdog`)
- HEARTBEAT: a cada 4h

## Repositórios GitHub Associados

- `living/livy-memory-bot` — este workspace
- `living/livy-bat-jobs` — BAT/ConectaBot observability
- `living/livy-delphos-jobs` — Delphos video vistoria
- `living/livy-tldv-jobs` — TLDV pipeline
- `living/livy-forge-platform` — Forge platform

## Credenciais

- Token GitHub: `GITHUB_PERSONAL_ACCESS_TOKEN` em `~/.openclaw/.env`
- claude-mem worker: `127.0.0.1:37777`

## Regras Aprendidas

- `add_frontmatter`: +1 (bom trabalho)
- `archive_file`: -1 (não archive ainda)

## Notas de Operação

- Topic files nunca expiram — se um projeto está ativo, o topic file permanece
- Decisões técnicas devem ser registradas em `memory/curated/` ao serem tomadas
- HEARTBEAT.md é o dashboard operacional — consultar em cada sessão
- Nunca exponha dados de clientes fora do contexto permitido

## Cross-references

- Infra: [openclaw-gateway.md](openclaw-gateway.md) — gateway que hospeda o agente
- Memória: [claude-mem-observations.md](claude-mem-observations.md) — camada 1 da memória
- Projetos: [forge-platform.md](forge-platform.md), [bat-conectabot-observability.md](bat-conectabot-observability.md), [delphos-video-vistoria.md](delphos-video-vistoria.md), [tldv-pipeline-state.md](tldv-pipeline-state.md)
