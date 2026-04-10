# Napkin - Livy Memory Agent

## Curation Rules
- Re-prioritize on every read.
- Keep recurring, high-value notes only.
- Max 10 items per category.
- Each item includes date + "Do instead".

## Execution & Validation (Highest Priority)

1. **[2026-04-10] Domain pipeline de revisão: spec → fix → spec recheck → CQ**
   Do instead: trate CQ como etapa final; se houver gap de spec (ex.: role fora do contrato), corrija e rode recheck antes de aprovar.

2. **[2026-04-10] Regra canônica de roles: `part_of` é proibido no domínio Living**
   Do instead: use apenas `author`, `reviewer`, `commenter`, `participant`, `assignee`, `decision_maker`; rode `grep -R "part_of" vault/` antes de fechar PR.

3. **[2026-04-10] Antes de declarar "done", exigir evidência E2E completa**
   Do instead: executar `python3 -m pytest vault/tests/ -q --tb=no` + `python3 -m vault.pipeline --dry-run -v` + `python3 -m vault.pipeline -v` e reportar números (ex.: 413 passed, gaps/orphans 0/0).

4. **[2026-04-10] Schema drift de sources detectado por domain_lint = migrar arquivo**
   Do instead: `missing_mapper_version` em domain_lint indica arquivo em formato legado; rodar `scripts/migrate_source_schema.py` (inclui decisions/ + entities/ + concepts/).

5. **[2026-04-05] Always clean untracked test artifacts before finalizing PR**
   Do instead: check `git status --short` for stray artifacts and remove noise before push/PR.

6. **[2026-04-05] Subagent-driven worktree: run pytest from inside skills dir**
   Do instead: `cd skills/memoria-consolidation && python3 -m pytest test_reconciliation.py -q` when validating hyphenated skill packages.

7. **[2026-04-01] Three test suites exist — run all after any change**
   Do instead: `python3 skills/X/test_X.py && python3 scripts/test_X.py && python3 scripts/test_security.py`.

8. **[2026-04-01] OpenClaw skills need YAML frontmatter with name + description**
   Do instead: every skill `SKILL.md` starts with valid frontmatter, or it won't be discovered.

9. **[2026-04-01] Supabase TLDV: `meetings` + `summaries`, NOT `meeting_memories`**
   Do instead: pull decisions/topics from canonical tables and treat `meeting_memories` as secondary.

10. **[2026-04-01] Token/secrets: fail-fast with ValueError**
   Do instead: assert required env vars up front; never hardcode credentials.

## Shell & Command Reliability

1. **[2026-04-10] `gh pr create` with markdown/backticks must use `--body-file`**
   Do instead: write PR text to temp file and call `gh pr create --body-file /tmp/pr.md` to avoid shell command substitution and mangled PR bodies.

2. **[2026-04-10] Subagent spawns fail with ACP-only fields**
   Do instead: for `runtime=subagent`, send minimal payload only; never include `streamTo`, `attachments`, `attachAs`.

3. **[2026-04-01] Python subprocesses don't inherit env vars - source + export first**
   Do instead: `source ~/.openclaw/.env && export SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY && python3 script.py`.

4. **[2026-04-01] Supabase REST API filter syntax differs from Python client**
   Do instead: use dot notation - `field.ilike.*{value}*`, `field.eq.{value}`, `field.gte.{value}`.

5. **[2026-04-01] Time-bounded cache needs manual implementation**
   Do instead: use `dict[key] = (value, timestamp)` with TTL checks.

6. **[2026-03-31] Feedback poller runs via systemd, not manually**
   Do instead: use `systemctl --user restart feedback-webhook.service`.

7. **[2026-03-31] Telegram callback_data use pipe separator, not colon**
   Do instead: format `feedback|{action_id}|{filename}|up`.

8. **[2026-03-31] Feedback poller: pkill before restart**
   Do instead: `pkill -f feedback_poller.py` before starting if needed.

## Telegram Feedback

1. **[2026-04-01] Adding new skill with feedback: three files to update**
   Do instead: (1) add prefix case in `feedback_poller.py` with `ALLOWED_USER_IDS` check, (2) add file path to `FEEDBACK_FILES` dict, (3) create isolated `memory/<skill>-feedback-log.jsonl`.

2. **[2026-03-31] Feedback message flow: document + summary/buttons separate**
   Do instead: send file as document (no buttons), then send summary + 👍👎 buttons in second message - Telegram callbacks don't fire from document captions.

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
   Do instead: confirm repo before pushing - similar names exist across the org.

2. **[2026-04-01] Canal `memory` = grupo Living Memory Observation**
   Do instead: memory-agent usa canal `memory` (conta própria, bot `@livy_agentic_memory_bot`). O grupo `-5158607302` (Living Memory Observation) recebe observações via SSE do claude-mem.

## TLDV Pipeline

1. **[2026-04-10] Runbook para decisões de daily: `meetings` → `summaries` em 3 passos**
   Do instead: buscar `meetings` por `name ilike.*daily*|*status*` + `enriched_at=not.is.null`, filtrar por `created_at`, coletar `meeting_id`, e consultar `summaries` para `topics`/`decisions` (fonte canônica).

2. **[2026-04-01] `enrichment_context` (PRs/Cards) é genérico - últimos 7 dias, não específico da reunião**
   Do instead: não treat PRs e Cards como Linked à reunião - são enrichment broad. `summaries.topics` e `summaries.decisions` são mais fiáveis.
