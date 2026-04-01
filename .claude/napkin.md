# Napkin — Livy Memory Agent

## Curation Rules
- Re-prioritize on every read.
- Keep recurring, high-value notes only.
- Max 10 items per category.
- Each item includes date + "Do instead".

## Execution & Validation (Highest Priority)

1. **[2026-04-01] Supabase schema: always verify actual columns first**
   Do instead: `GET /rest/v1/table_name?select=*&limit=3` — never trust schema docs or specs without verification. Schema mismatch causes total rework.

2. **[2026-04-01] Three test suites exist — run all after any change**
   Do instead: `python3 skills/X/test_X.py && python3 scripts/test_X.py && python3 scripts/test_security.py` — all three must pass before commit.

3. **[2026-04-01] Token/secrets: fail-fast with ValueError**
   Do instead: `token = os.getenv("X_TOKEN", ""); assert token, "X_TOKEN not set"` — never hardcode, never let it silently use wrong value.

4. **[2026-03-31] Always read identity files before any operation**
   Do instead: read `.claude/SOUL.md` + `.claude/IDENTITY.md` first, then `MEMORY.md` as index.

5. **[2026-03-31] MEMORY.md is an index, not a dump**
   Do instead: never edit MEMORY.md directly for content — update topic files in `memory/curated/` instead.

6. **[2026-03-31] Topic files go in `memory/curated/`, not root**
   Do instead: store curated project context in `memory/curated/<slug>.md` with YAML frontmatter.

## Shell & Command Reliability

1. **[2026-04-01] Supabase REST API filter syntax differs from Python client**
   Do instead: use dot notation — `field.ilike.*{value}*`, `field.eq.{value}`, `field.gte.{value}` — not Python client chaining.

2. **[2026-04-01] Time-bounded cache needs manual implementation**
   Do instead: use `dict[key] = (value, timestamp)` with TTL check — `lru_cache` has no TTL enforcement.

3. **[2026-03-31] Feedback poller runs via systemd, not manually**
   Do instead: use `systemctl --user restart feedback-webhook.service` — manual execution creates duplicate processes causing 409 Conflict.

4. **[2026-03-31] Telegram callback_data use pipe separator, not colon**
   Do instead: format `feedback|{action_id}|{filename}|up` — colon splits break filenames with dots.

5. **[2026-03-31] Feedback poller: pkill before restart**
   Do instead: always `pkill -f feedback_poller.py` before starting.

## Telegram Feedback

1. **[2026-04-01] Adding new skill with feedback: three files to update**
   Do instead: (1) add prefix case in `feedback_poller.py` with `ALLOWED_USER_IDS` check, (2) add file path to `FEEDBACK_FILES` dict, (3) create isolated `memory/<skill>-feedback-log.jsonl`.

2. **[2026-03-31] Feedback message flow: document + summary/buttons separate**
   Do instead: send file as document (no buttons), then send summary + 👍👎 buttons in second message — Telegram callbacks don't fire from document captions.

3. **[2026-03-31] Feedback context enrichment: learned-rules + memory search**
   Do instead: autoresearch reads `learned-rules.md` and searches memory for each file.

## Memory Consolidation

1. **[2026-03-31] Consolidation is 4-phase: Orientation → Gather Signal → Consolidation → Prune & Index**
   Do instead: run `python3 skills/memoria-consolidation/consolidate.py`.

2. **[2026-03-31] Lock file prevents concurrent consolidation runs**
   Do instead: if lock error appears, check `memory/.consolidation.lock` and remove if stale.

3. **[2026-03-31] Stale threshold: >60 days → archive, 30-60 days → monitor**
   Do instead: files older than 60 days are moved to `memory/.archive/`, not deleted.

## GitHub Context

1. **[2026-03-31] Repo `living/livy-memory-bot` is this workspace**
   Do instead: confirm repo before pushing — similar names exist across the org.
