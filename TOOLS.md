# TOOLS.md - Livy Memory Agent Tools

## Memória

| Ferramenta | Path | Uso |
|---|---|---|
| claude-mem | `~/.claude-mem/` | Observations (SQLite) |
| MEMORY.md | `MEMORY.md` | Índice curado |
| Topic files | `memory/curated/*.md` | Contexto por projeto |
| consolidation-log | `memory/consolidation-log.md` | Log da consolidação |

## Runbook — Buscar memórias de decisões nas daylies (TLDV)

**Fonte canônica:** `meetings` + `summaries` (não usar `meeting_memories` como primária)

1. Buscar reuniões em `meetings` por nome (`ilike.*daily*` ou `ilike.*status*`) com `enriched_at=not.is.null`
2. Filtrar por período (`created_at`) e coletar `meeting_id`
3. Consultar `summaries` por `meeting_id` e extrair `topics` + `decisions`

Exemplo rápido (REST):

```bash
# 1) meetings
GET /rest/v1/meetings?select=id,name,created_at,enriched_at&enriched_at=not.is.null&name=ilike.*daily*&order=created_at.desc&limit=20

# 2) summaries por meeting_id
GET /rest/v1/summaries?select=meeting_id,topics,decisions,tags&meeting_id=in.(<id1>,<id2>,...)
```

**Observação:** `enrichment_context` (PRs/cards) é contexto amplo; para decisão de reunião, priorizar `summaries.decisions`.

## Scripts

- `skills/memoria-consolidation/consolidate.py` — Auto Dream adaptado
- Run: `python3 skills/memoria-consolidation/consolidate.py`

## OpenClaw CLI

```bash
openclaw gateway status
openclaw channels status
openclaw cron list
```

## Repositórios GitHub

- `living/livy-memory-bot` — este workspace
- `living/livy-bat-jobs` — BAT/ConectaBot observability
- `living/livy-delphos-jobs` — Delphos video vistoria
- `living/livy-tldv-jobs` — TLDV pipeline
- `living/livy-forge-platform` — Forge platform

## Credenciais

- Token GitHub: `GITHUB_PERSONAL_ACCESS_TOKEN` em `~/.openclaw/.env`
- claude-mem worker: `127.0.0.1:37777`
