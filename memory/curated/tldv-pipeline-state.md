---
name: tldv-pipeline-state
description: Pipeline de transcrição e sumário de reuniões via API tl;dv
type: pipeline
date: 2026-03-30
project: livy-tldv-jobs
status: aguardando_token
decision: Token JWT expirado — gw.tldv.io 502 Bad Gateway. Renovação pendente.
---

# TLDV Pipeline

## Repo

`living/livy-tldv-jobs`

## Problema Conhecido (2026-03-30)

**Token JWT Expirado**

- **Sintoma:** gw.tldv.io retorna `502 Bad Gateway`
- **Impacto:** meetings com blobs expirados no Azure travam em `UNARCHIVE_REQUESTED`
- **Ação pendente:** renovação do token JWT do tl;dv
- **Status:** Aguardando token

## Décorredores

| Data | Evento |
|---|---|
| 2026-03-30 | Token JWT expirado identificado. gw.tldv.io 502. Ação: renovação de token pendente. |

## Cross-references

- Relacionado: [bat-conectabot-observability.md](bat-conectabot-observability.md) — ambos são pipelines com Sev2/problems
- Relacionado: [livy-memory-agent.md](livy-memory-agent.md) — agente monitora este pipeline via cron jobs
