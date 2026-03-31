---
name: claude-mem-observations
description: Camada de observações agênticas via claude-mem (SQLite) — camada 1 do sistema de memória de 3 camadas
type: memory-layer
date: 2026-03-31
project: claude-mem
status: ativo
decision: claude-mem é a fonte canônica de decisões agênticas — observations destiladas em topic files durante consolidação
---

# claude-mem Observations

## Fonte

- **Path:** `~/.claude-mem/claude-mem.db`
- **Formato:** SQLite
- **Worker:** `127.0.0.1:37777`

## Papel na Arquitetura de Memória

claude-mem é a **camada 1** (observations) do sistema de memória agêntica de 3 camadas:

| Camada | Fonte | Path |
|---|---|---|
| 1 — Observations | claude-mem SQLite | `~/.claude-mem/claude-mem.db` |
| 2 — Curated | Topic files | `memory/curated/*.md` |
| 3 — Operational | HEARTBEAT + logs | `HEARTBEAT.md`, `memory/consolidation-log.md` |

## Notas de Operação

- cluade-mem é a fonte canônica de decisões agênticas
- Observations são destiladas em topic files durante consolidação
- Worker conectado em `127.0.0.1:37777`

## Décorredores

| Data | Evento |
|---|---|
| 2026-03-31 | Sistema de memória de 3 camadas documentado e implementado. |

## Regras de Curadoria

- Topic files em `memory/curated/` devem refletir decisões extraídas das observations
- Decisões > opinions: não sugira, destile contexto
- Nunca exponha dados de clientes fora do contexto permitido

## Cross-references

- Camada 2: [livy-memory-agent.md](livy-memory-agent.md) — agente que gerencia consolidação das observations
