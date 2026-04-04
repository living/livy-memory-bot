---
name: livy-evo
description: Agente evolutivo da Living Consultoria — monitoramento e análise de genealogia de código
type: agent
date: 2026-03-31
project: livy-evo
status: conforme_cronograma
decision: Agente evo operando conforme cronograma — cron daily às 02h BRT
---

# livy-evo

## Status

Conforme cronograma.

## Cron Jobs Associados

| Job | Schedule | Descrição |
|---|---|---|
| `evo-analyze` | 02h BRT daily | Análise evolutiva |
| `evo-watchdog` | 08h BRT daily | Verificação de integridade |

## Décorredores

| Data | Evento |
|---|---|
| 2026-03-31 | Agente operando conforme cronograma. |

## Cross-references

- Relacionado: [livy-memory-agent.md](livy-memory-agent.md) — ambos são agentes Living com cron jobs
- Relacionado: [forge-platform.md](forge-platform.md) — plataforma pode usar análise evo
