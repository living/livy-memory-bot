# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

This is the **Livy Memory Agent** workspace — an agentic memory system for Living Consultoria. It maintains a 3-layer memory architecture for institutional context:

| Layer | Source | Format |
|-------|--------|--------|
| Observations | `~/.claude-mem/claude-mem.db` | SQLite |
| Curated | `MEMORY.md` + `memory/curated/*.md` | Markdown |
| Operational | `HEARTBEAT.md` + `memory/consolidation-log.md` | Markdown |

## Feedback Learning

`learn_from_feedback.py` runs at START of autoresearch_cron.py, reads `memory/feedback-log.jsonl`, generates `memory/learned-rules.md`. No separate cron needed — feedback accumulates between autoresearch runs.

## Memory Consolidation

Run the 4-phase consolidation script:

```bash
python3 skills/memoria-consolidation/consolidate.py
```

Phases: Orientation → Gather Signal → Consolidation → Prune & Index
Log output: `memory/consolidation-log.md`
**Mente Coletiva:** consolidation processes BOTH workspaces: memory-agent + Livy Deep (main). Both MEMORY.md indexes are validated (<200 lines).

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
**Cron run:** `openclaw cron run <id>` (no --force flag — it runs immediately)
**Cron DM delivery:** `--announce --to tg:7426291192` for user DM

**Bot:** `@livy_agentic_memory_bot` (feedback) — DM to report actions with 👍/👎 buttons
**Autoresearch cron ID:** `0c388629-3465-4825-a791-16c46c9d1300` (every 1h, memory-agent)
**Feedback cron:** memory-agent-feedback-learn (cron ID aa5cd560, at :45) — processes accumulated feedback before each autoresearch run

## Infrastructure

**Telegram bot tokens:** OpenClaw gateway (`8738927361:AAE2COOt...`) conflicts with manual getUpdates — use separate bot `8725269523:AAFqAFEF...` for polling only
**Telegram polling:** Use `getUpdates` polling only — webhook conflicts with getUpdates (409 Conflict) and is blocked by DNS issues on this server
**Caddyfile:** `/home/lincoln/.local/etc/caddy/Caddyfile` — `/memory-callback/` active; `/telegram-feedback/` route removed (was unused)
**Test feedback:** Send test message via API, click button, verify with `tail memory/feedback-log.jsonl`
**Telegram getUpdates:** Calling via curl consumes pending updates from Telegram — use for testing only, not in production polling code
**Systemd user services:** `~/.config/systemd/user/<name>.service` — control with `systemctl --user <start|stop|status>`
**Feedback poller:** Managed by `feedback-webhook.service` (systemd). Use `systemctl --user restart feedback-webhook.service` — do NOT run manually (creates duplicate processes causing 409 Conflict)
**Feedback context:** `learned-rules.md` + `openclaw memory search` enrich each file summary before sending — negative rules shown as warnings in summary message
**Consolidation output:** "DRY RUN" + "mudanças pendentes" messages are informational only — changes ARE applied if pending count > 0
**Autoresearch script:** `python3 scripts/autoresearch_cron.py` — sends files via Telegram Direct API with feedback buttons, processes feedback at start
**Dream:** `python3 skills/memoria-consolidation/dream_all.py` — processes sessions from main (Livy Deep) and both memory workspaces
