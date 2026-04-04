---
name: bat-conectabot-observability
description: Pipeline de observabilidade do ConectaBot (BAT — Built After Today) com webhook causando Sev2 elevado
type: observability
date: 2026-03-30
project: livy-bat-jobs
status: monitorando
decision: Sev2 elevado (~2200 erros/ciclo 6h) causado por webhook do ConectaBot — comportamento esperado, monitorando
---

# BAT / ConectaBot Observability

## Repo

`living/livy-bat-jobs`

## Problema Conhecido (2026-03-30)

**Sev2 Elevado — 2200 erros a cada 6h**

- **Causa:** webhook do ConectaBot (comportamento esperado)
- **Gravidade:** Sev2
- **Volume:** ~2200 erros por ciclo de 6h
- **Status:** Monitorando — não é bug, mas volume elevado

## Décorredores

| Data | Evento |
|---|---|
| 2026-03-30 | Sev2 elevado identificado. Webhook do ConectaBot como causa. Monitorando. |

## Cross-references

- Relacionado: [tldv-pipeline-state.md](tldv-pipeline-state.md) — ambos são pipelines de jobs com problemas documentados
- Relacionado: [livy-memory-agent.md](livy-memory-agent.md) — agente que monitora este pipeline
