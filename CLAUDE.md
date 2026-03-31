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
