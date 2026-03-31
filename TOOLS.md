# TOOLS.md - Livy Memory Agent Tools

## Memória

| Ferramenta | Path | Uso |
|---|---|---|
| claude-mem | `~/.claude-mem/` | Observations (SQLite) |
| MEMORY.md | `MEMORY.md` | Índice curado |
| Topic files | `memory/curated/*.md` | Contexto por projeto |
| consolidation-log | `memory/consolidation-log.md` | Log da consolidação |

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
