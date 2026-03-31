# Napkin — Livy Memory Agent

## Curation Rules
- Re-prioritize on every read.
- Keep recurring, high-value notes only.
- Max 10 items per category.
- Each item includes date + "Do instead".

## Execution & Validation (Highest Priority)

1. **[2026-03-31] Always read identity files before any operation**
   Do instead: read `.claude/SOUL.md` + `.claude/IDENTITY.md` first, then `MEMORY.md` as index.

2. **[2026-03-31] MEMORY.md is an index, not a dump**
   Do instead: never edit MEMORY.md directly for content — update topic files in `memory/curated/` instead.

3. **[2026-03-31] Topic files go in `memory/curated/`, not root**
   Do instead: store curated project context in `memory/curated/<slug>.md` with YAML frontmatter.

## Shell & Command Reliability

1. **[2026-03-31] Feedback poller runs via systemd, not manually**
   Do instead: use `systemctl --user restart feedback-webhook.service` — manual execution creates duplicate processes causing 409 Conflict.

2. **[2026-03-31] Telegram callback_data use pipe separator, not colon**
   Do instead: format `feedback|{action_id}|{filename}|up` — colon splits break filenames with dots (e.g., `bat-conectabot-observability.md`).

3. **[2026-03-31] Feedback poller: pkill before restart**
   Do instead: always `pkill -f feedback_poller.py` before starting — duplicate processes cause 409 Conflict.

## Telegram Feedback

1. **[2026-03-31] Feedback message flow: document + summary/buttons separate**
   Do instead: send file as document (no buttons), then send summary + 👍👎 buttons in second message — Telegram callbacks don't fire from document captions.

2. **[2026-03-31] Feedback context enrichment: learned-rules + memory search**
   Do instead: autoresearch reads `learned-rules.md` and searches memory for each file — negative rules shown as warnings in summary.

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
