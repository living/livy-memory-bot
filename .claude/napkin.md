# Napkin — Livy Memory Agent

## Curation Rules
- Re-prioritize on every read.
- Keep recurring, high-value notes only.
- Max 10 items per category.
- Each item includes date + "Do instead".

## Startup Sequence (Highest Priority)

1. **[2026-03-31] Always read identity files before any operation**
   Do instead: read `.claude/SOUL.md` + `.claude/IDENTITY.md` first, then `MEMORY.md` as index.

2. **[2026-03-31] MEMORY.md is an index, not a dump**
   Do instead: never edit MEMORY.md directly for content — update topic files in `memory/curated/` instead.

3. **[2026-03-31] Topic files go in `memory/curated/`, not root**
   Do instead: store curated project context in `memory/curated/<slug>.md` with YAML frontmatter.

## Memory Consolidation

1. **[2026-03-31] Consolidation is 4-phase: Orientation → Gather Signal → Consolidation → Prune & Index**
   Do instead: run `python3 skills/memoria-consolidation/consolidate.py` — always reads from MEMORY.md index.

2. **[2026-03-31] Lock file prevents concurrent consolidation runs**
   Do instead: if lock error appears, check `memory/.consolidation.lock` and remove if stale (no running process).

3. **[2026-03-31] Stale threshold: >60 days → archive, 30-60 days → monitor**
   Do instead: files older than 60 days are moved to `memory/.archive/`, not deleted.

## GitHub Context

1. **[2026-03-31] Repo `living/livy-memory-bot` is this workspace**
   Do instead: confirm repo before pushing — this workspace and `living/livy-meetings` have similar names but different purposes.

## Domain Behavior

1. **[2026-03-31] This workspace is agent memory infra, not application code**
   Do instead: no build/test commands — primary actions are reading/writing markdown files and running consolidation.
