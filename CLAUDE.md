# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

This is the **Livy Memory Agent** workspace — an agentic memory system for Living Consultoria. It maintains a 3-layer memory architecture for institutional context:

| Layer | Source | Format |
|-------|--------|--------|
| Observations | `~/.claude-mem/claude-mem.db` | SQLite |
| Curated | `MEMORY.md` + `memory/curated/*.md` | Markdown |
| Operational | `HEARTBEAT.md` + `memory/consolidation-log.md` | Markdown |

## Memory Consolidation

Run the 4-phase consolidation script:

```bash
python3 skills/memoria-consolidation/consolidate.py
```

Phases: Orientation → Gather Signal → Consolidation → Prune & Index
Log output: `memory/consolidation-log.md`

## File Structure

```
memory/                    # Curated long-term memory
├── curated/               # Topic files by project/agent
│   └── *.md
├── .archive/              # Stale files (>60 days, moved here)
└── consolidation-log.md   # Last consolidation output

.claude/                   # Identity files (read at session start)
├── SOUL.md
├── IDENTITY.md
└── AGENTS.md
```

## Topic Files

Topic files in `memory/curated/` contain detailed project/agent context. They are referenced from `MEMORY.md`. Keep `MEMORY.md` under 200 lines — push details to topic files.

## Operational Rules

- Read `.claude/SOUL.md` and `.claude/IDENTITY.md` at session start
- Read `MEMORY.md` as the curated memory index
- When encountering technical decisions: update the relevant topic file
- When encountering stale entries: register for consolidation
- `HEARTBEAT.md` is the operational dashboard — keep it current

## OpenClaw Automation

**Cron jobs:** `openclaw cron list` / `openclaw cron add` / `openclaw cron run <id>` / `openclaw cron edit <id>`
**Cron timeout flag:** `--timeout-seconds` (not `--timeout`)
**Cron DM delivery:** `--announce --to tg:7426291192` for user DM

**Bot:** `@livy_agentic_memory_bot` (feedback) — DM to report actions with 👍/👎 buttons
**Autoresearch cron ID:** `0c388629-3465-4825-a791-16c46c9d1300` (every 1h, memory-agent)
**Learn cron ID:** `f5969901-00ba-449f-989b-b2b972b70a79` (23h BRT, memory-agent)

## Infrastructure

**Telegram bot tokens:** OpenClaw gateway (`8738927361:AAE2COOt...`) conflicts with manual getUpdates — use separate bot `8725269523:AAFqAFEF...` for webhooks/polling
**Telegram webhook:** register via `curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" -d "url=<url>"`
**Caddyfile:** `/home/lincoln/.local/etc/caddy/Caddyfile` — reload with `caddy reload --config <path> --adapter caddyfile`
**Systemd user services:** `~/.config/systemd/user/<name>.service` — control with `systemctl --user <start|stop|status>`
**Feedback webhook:** runs on port 8080, endpoint `https://srv1405423.hstgr.cloud/telegram-feedback/`
