# Evo Wiki Research (Fase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar Fase 2 do Evo Wiki Research com stream Trello (polling board↔projeto) e stream self-healing write-mode agressivo no mesmo PR, com gates internos e critérios auditáveis.

**Architecture:** Duas streams paralelas no mesmo branch: Stream T (Trello ingest + mapping + cron) e Stream S (self-healing apply/rollback/circuit-breaker). A integração é controlada por gates internos: T1 -> S1 -> Final. O SSOT permanece em `state/identity-graph/state.json`; caches por fonte em `.research/<source>/state.json` seguem derivadas.

**Tech Stack:** Python 3, pytest, OpenClaw cron, JSON/JSONL append-only, módulos `vault/research` e `vault/crons`.

---

## File Structure

### Create
- `vault/research/trello_client.py` — polling de cards/actions por board
- `vault/research/self_healing.py` — apply/rollback/circuit-breaker core
- `vault/research/trello_mapper.py` — board↔project e status/list semantics
- `vault/crons/research_trello_cron.py` — runner cron da fonte Trello
- `tests/research/test_trello_client.py`
- `tests/research/test_pipeline_trello.py`
- `tests/research/test_trello_board_project_map.py`
- `tests/research/test_self_healing_apply.py`
- `tests/research/test_self_healing_rollback.py`
- `tests/research/test_circuit_breaker.py`

### Modify
- `vault/research/pipeline.py` — adicionar branch `source="trello"`, event_key collision-safe
- `vault/research/state_store.py` — incluir `trello` em state/metrics + retention checks
- `vault/research/retry_policy.py` — classificar availability errors sem contaminar quality streak
- `vault/crons/__init__.py` — export `run_research_trello`
- `vault/crons/research_consolidation_cron.py` — resolver `pending_conflicts` e self-healing metrics schema validation
- `vault/schemas/trello-board-project-map.yaml` — mapping board→project versionado
- `HEARTBEAT.md` — adicionar cron `research-trello` + playbook breaker/offline
- `MEMORY.md` — registrar decisão Fase 2 implementada
- `memory/curated/livy-memory-agent.md` — registrar operação Fase 2

---

### Task 1: Bootstrap Trello client (polling por board)

**Files:**
- Create: `vault/research/trello_client.py`
- Test: `tests/research/test_trello_client.py`

- [ ] **Step 1: Write failing test para fetch de cards por board**
```python
def test_fetch_cards_since_uses_board_ids_and_returns_normalized_items():
    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])
    # mock HTTP response
    events = client.fetch_events_since(None)
    assert isinstance(events, list)
```

- [ ] **Step 2: Run test to verify RED**
Run: `PYTHONPATH=. pytest -q tests/research/test_trello_client.py::test_fetch_cards_since_uses_board_ids_and_returns_normalized_items -v`
Expected: FAIL (`TrelloClient` missing)

- [ ] **Step 3: Implement minimal `TrelloClient`**
```python
class TrelloClient:
    def __init__(self, api_key: str, token: str, board_ids: list[str]): ...
    def fetch_events_since(self, last_seen_at: str | None) -> list[dict]: ...
```

Verify env vars at init:
```python
api_key = os.environ.get("TRELLO_API_KEY")
token = os.environ.get("TRELLO_TOKEN")
board_ids = os.environ.get("TRELLO_BOARD_IDS", "").split(",")
if not api_key or not token:
    raise EnvironmentError("TRELLO_API_KEY and TRELLO_TOKEN must be set")
```

- [ ] **Step 4: Run targeted tests to verify GREEN**
Run: `PYTHONPATH=. pytest -q tests/research/test_trello_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/trello_client.py tests/research/test_trello_client.py
git commit -m "feat(research): add Trello polling client for board events"
```

### Task 2: Trello event_key collision-safe strategy

**Files:**
- Modify: `vault/research/pipeline.py`
- Test: `tests/research/test_pipeline_trello.py`

- [ ] **Step 1: Write failing tests for event_key uniqueness when action_id missing**
```python
def test_trello_card_updated_without_action_id_uses_deterministic_fallback():
    # same card, different field/timestamp -> different event_key
    assert k1 != k2
```

- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_pipeline_trello.py::test_trello_card_updated_without_action_id_uses_deterministic_fallback -v`
Expected: FAIL

- [ ] **Step 3: Implement deterministic fallback hierarchy in pipeline event_key builder**
Exact suffix order (use first applicable):
1. `action_id` (if present and non-empty)
2. `list_id_at_event + "_" + updated_at_ts` (for card_created/card_updated)
3. `target_list_id + "_" + card_id + "_" + timestamp` (for list_moved)
4. `member_id + "_" + timestamp` (for member_added/member_removed)
5. `hash16(field1 + "_" + field2 + "_" + timestamp)` — last resort to avoid `::`

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_pipeline_trello.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/pipeline.py tests/research/test_pipeline_trello.py
git commit -m "feat(research): add collision-safe Trello event key strategy"
```

### Task 3: Board↔Project map resolver

**Files:**
- Create: `vault/research/trello_mapper.py`
- Modify: `vault/schemas/trello-board-project-map.yaml`
- Test: `tests/research/test_trello_board_project_map.py`

- [ ] **Step 1: Write failing tests for board->project mapping and unknown board behavior**
- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_trello_board_project_map.py -v`
Expected: FAIL

- [ ] **Step 3: Implement mapping loader + resolver**
- unknown board -> `mapping_missing` flag, no write
- known board -> return project source_key

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_trello_board_project_map.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/trello_mapper.py vault/schemas/trello-board-project-map.yaml tests/research/test_trello_board_project_map.py
git commit -m "feat(research): add Trello board-project mapper"
```

### Task 4: Trello pipeline integration (cards, list moves, members)

**Files:**
- Modify: `vault/research/pipeline.py`
- Test: `tests/research/test_pipeline_trello.py`

- [ ] **Step 1: Write failing integration tests for three event families**
- card_created/card_updated -> evidence markdown
- list_moved -> status transition
- member_added/removed -> identity reinforcement event

- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_pipeline_trello.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `source="trello"` branch in `ResearchPipeline.run()`**
Normalization rules per event type:
- `card_created`: write evidence markdown to `memory/vault/entities/cards/{card_id}.md`
- `card_updated`: upsert card entity with latest fields
- `list_moved`: parse `listBefore`/`listAfter` and emit status transition old→new
- `member_added`: emit identity reinforcement linking `member_id` to person candidate
- `member_removed`: emit weakly-deprecating unlink event (no hard delete)

Pipeline sequence: poll -> normalize -> dedupe -> context -> resolve -> hypothesize -> validate -> apply -> verify -> state persist + rebuild `.research/trello/state.json`

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_pipeline_trello.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/pipeline.py tests/research/test_pipeline_trello.py
git commit -m "feat(research): integrate Trello stream into research pipeline"
```

### Task 5: Add `research_trello` cron

**Files:**
- Create: `vault/crons/research_trello_cron.py`
- Modify: `vault/crons/__init__.py`
- Test: `tests/research/test_pipeline_trello.py`

- [ ] **Step 1: Write failing smoke test for trello cron entrypoint**
- [ ] **Step 2: Run test (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_pipeline_trello.py::test_research_trello_cron_runs_with_lock -v`
Expected: FAIL

- [ ] **Step 3: Implement cron with lock + env interval + run summary**
- env: `RESEARCH_TRELLO_INTERVAL_MIN` default 20
- lock path: `.research/trello/lock`
- call `ResearchPipeline(source="trello")`

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_pipeline_trello.py::test_research_trello_cron_runs_with_lock -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/crons/research_trello_cron.py vault/crons/__init__.py tests/research/test_pipeline_trello.py
git commit -m "feat(crons): add research_trello cron runner"
```

### Task 6: Self-healing apply core (aggressive mode >=0.70)

**Files:**
- Create: `vault/research/self_healing.py`
- Test: `tests/research/test_self_healing_apply.py`

- [ ] **Step 1: Write failing tests for confidence thresholds**
- >=0.85 auto-apply
- 0.70-0.84 auto-apply + emit verbose log entry (source, confidence, decision)
- 0.45-0.69 queue for review
- <0.45 drop silently

Also test env var gating:
- `SELF_HEALING_WRITE_ENABLED=false` -> all writes dry-run
- `SELF_HEALING_AGGRESSIVE_MODE=false` -> skip auto-apply even if confidence high
- `SELF_HEALING_BREAKER_ENABLED=false` -> breaker never transitions to paused

- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_self_healing_apply.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `apply_decision()` in self_healing module**
Read and gate on env vars:
```python
write_enabled = os.environ.get("SELF_HEALING_WRITE_ENABLED", "true").lower() == "true"
aggressive = os.environ.get("SELF_HEALING_AGGRESSIVE_MODE", "true").lower() == "true"
breaker_enabled = os.environ.get("SELF_HEALING_BREAKER_ENABLED", "true").lower() == "true"
```
If not write_enabled: accumulate evidence but do not apply.
If not aggressive: only auto-apply >=0.85 (skip 0.70-0.84 verbose mode).
If not breaker_enabled: skip breaker transition checks.

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_self_healing_apply.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/self_healing.py tests/research/test_self_healing_apply.py
git commit -m "feat(research): add self-healing aggressive apply policy"
```

### Task 7: Append-only rollback engine

**Files:**
- Modify: `vault/research/self_healing.py`
- Modify: `vault/logs/experiments.jsonl`
- Test: `tests/research/test_self_healing_rollback.py`

- [ ] **Step 1: Write failing rollback tests (append-only invariant)**
- include explicit test `test_rollback_never_edits_existing_lines`
- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_self_healing_rollback.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `rollback_append()` with supersedes linkage**
- output includes event_key, supersedes, reason, breaker_mode

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_self_healing_rollback.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/self_healing.py tests/research/test_self_healing_rollback.py
git commit -m "feat(research): add append-only rollback engine"
```

### Task 8: Circuit breaker + metrics schema

**Files:**
- Modify: `vault/research/self_healing.py`
- Modify: `vault/crons/research_consolidation_cron.py`
- Test: `tests/research/test_circuit_breaker.py`

- [ ] **Step 1: Write failing tests for breaker transitions**
- 3 quality errors -> write_paused(source)
- 5 reverts in 10 runs -> global_paused
- availability_error increments separately

- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_circuit_breaker.py -v`
Expected: FAIL

- [ ] **Step 3: Implement breaker state machine + metrics schema writer**
- file: `state/identity-graph/self_healing_metrics.json`
- include exact fields: `revert_streak_by_source`, `error_streak_by_source`, `availability_error_by_source`
- validate schema in consolidation cron
- emit breaker transitions to `vault/logs/experiments.jsonl` in JSONL format (`ts`, `source`, `breaker_mode`, `decision`, `reason`)

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_circuit_breaker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/self_healing.py vault/crons/research_consolidation_cron.py tests/research/test_circuit_breaker.py
git commit -m "feat(research): add self-healing circuit breaker and metrics"
```

### Task 9: State store updates for Trello + retention guards

**Files:**
- Modify: `vault/research/state_store.py`
- Test: `tests/research/test_state_store.py`

- [ ] **Step 1: Write failing tests for `trello` source keys/last_seen and retention behavior**
- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_state_store.py -v`
Expected: FAIL

- [ ] **Step 3: Implement trello-aware state metrics + pending_conflicts alert threshold (200)**
- implement `pending_conflicts` resolver in consolidation:
  1. reapply source priority + recency
  2. keep pending on tie
  3. append `status: resolved` + `resolved_by_event_key` when resolved
- if `len(pending_conflicts) > 200`, emit alert entry in consolidation log

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_state_store.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/research/state_store.py tests/research/test_state_store.py
git commit -m "feat(research): extend state store for Trello and conflict retention guards"
```

### Task 10: Gate T1 verification (Trello)

**Files:**
- Verify only

- [ ] **Step 1: Run required T1 suites**
Run: `PYTHONPATH=. pytest -q tests/research/test_trello_client.py tests/research/test_pipeline_trello.py tests/research/test_trello_board_project_map.py`
Expected: 0 failures

- [ ] **Step 2: Run cron smoke**
Run: `python3 vault/crons/research_trello_cron.py`
Expected: status success + lock acquire/release

- [ ] **Step 3: Commit verification note (optional docs snapshot)**
```bash
git commit --allow-empty -m "chore(gate): pass T1 Trello gate"
```

### Task 11: Gate S1 verification (self-healing)

**Files:**
- Verify only

- [ ] **Step 1: Run required S1 suites**
Run: `PYTHONPATH=. pytest -q tests/research/test_self_healing_apply.py tests/research/test_self_healing_rollback.py tests/research/test_circuit_breaker.py`
Expected: 0 failures

- [ ] **Step 2: Validate metrics schema existence and shape**
Run: `python3 - <<'PY'
import json
p='state/identity-graph/self_healing_metrics.json'
obj=json.load(open(p))
for k in ['mode','paused_sources','apply_count_by_source','rollback_count_by_source','revert_streak_by_source','error_streak_by_source','availability_error_by_source']:
    assert k in obj
print('OK')
PY`
Expected: OK

- [ ] **Step 3: Commit verification note**
```bash
git commit --allow-empty -m "chore(gate): pass S1 self-healing gate"
```

### Task 11b: Watchdog integration (evo observation loop)

**Files:**
- Modify: `vault/crons/research_consolidation_cron.py`
- Test: `tests/research/test_consolidation_loop.py`

- [ ] **Step 1: Write failing test for watchdog observation loop**
- test that consolidation reads `self_healing_metrics.json` and evaluates:
  - revert rate >5% -> alert
  - pending_review backlog >50 -> alert
  - 3 consecutive revert cycles >10% -> global pause trigger

- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_consolidation_loop.py -v`
Expected: FAIL

- [ ] **Step 3: Implement watchdog observation in `research_consolidation_cron.py`**
After each consolidation run:
1. read `state/identity-graph/self_healing_metrics.json`
2. evaluate revert rate, backlog size, error streaks
3. if threshold crossed: emit alert to consolidation log + update breaker state
4. append decision to `vault/logs/experiments.jsonl`

- [ ] **Step 4: Run tests (GREEN)**
Run: `PYTHONPATH=. pytest -q tests/research/test_consolidation_loop.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add vault/crons/research_consolidation_cron.py tests/research/test_consolidation_loop.py
git commit -m "feat(research): add evo watchdog observation loop in consolidation"
```

### Task 12: Final regression + docs + operational registration

**Files:**
- Modify: `HEARTBEAT.md`, `MEMORY.md`, `memory/curated/livy-memory-agent.md`, `.claude/napkin.md` (local runbook)

- [ ] **Step 1: Run full research + regression suites**
Run: `PYTHONPATH=. pytest -q tests/research/`
Expected: 0 failures

Run: `PYTHONPATH=. pytest -q vault/tests/test_identity_resolution.py vault/tests/test_resilience.py --ignore=vault/tests/test_reverify_module.py`
Expected: 0 failures

- [ ] **Step 2: Smoke 4 crons**
Run:
- `python3 vault/crons/research_tldv_cron.py`
- `python3 vault/crons/research_github_cron.py`
- `python3 vault/crons/research_trello_cron.py`
- `python3 vault/crons/research_consolidation_cron.py`
Expected: all success

- [ ] **Step 3: Register `research-trello` cron in OpenClaw + document ID**
Run:
```bash
openclaw cron add \
  --name "research-trello" \
  --command "python3 vault/crons/research_trello_cron.py" \
  --schedule "*/20 * * * *" \
  --workspace /home/lincoln/.openclaw/workspace-livy-memory \
  --timeout 600 \
  --isolated
```
Then capture the cron ID returned and record it in HEARTBEAT.md under the `research-trello` job entry.

- [ ] **Step 4: Update memory docs (STM/LTM/napkin)**
- HEARTBEAT current timestamp and incidents
- MEMORY decision log for phase 2 go-live
- topic file with architecture delta
- napkin recurring lessons

- [ ] **Step 5: Commit final integration**
```bash
git add HEARTBEAT.md MEMORY.md memory/curated/livy-memory-agent.md docs/superpowers/specs/2026-04-18-evo-wiki-research-phase2-design.md docs/superpowers/plans/2026-04-18-evo-wiki-research-phase2-implementation.md
git commit -m "feat(research): complete evo wiki research phase 2 rollout"
```

---

## Execution Notes

- Maintain branch isolation (use a dedicated worktree for implementation).
- Follow TDD strictly per task: RED -> GREEN -> COMMIT.
- Keep append-only semantics for any rollback/supersession writes.
- Do not modify raw ingestion sources (`vault/data/**`, `data/**`, `exports/**`).
