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

- [ ] **Step 3: Implement deterministic fallback in pipeline event_key builder**
- required suffix order: action_id > list_id+updated_at > hash16(field1+field2+timestamp)

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
- poll Trello client
- normalize payload
- dedupe
- context/resolve/hypothesis/validate/apply
- persist state + rebuild `.research/trello/state.json`

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
- 0.70-0.84 auto-apply verbose
- 0.45-0.69 queue
- <0.45 drop

- [ ] **Step 2: Run tests (RED)**
Run: `PYTHONPATH=. pytest -q tests/research/test_self_healing_apply.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `apply_decision()` in self_healing module**

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
- Modify: `memory/consolidation-log.md` (runtime output)
- Test: `tests/research/test_self_healing_rollback.py`

- [ ] **Step 1: Write failing rollback tests (append-only invariant)**
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
- validate schema in consolidation cron

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
for k in ['mode','paused_sources','apply_count_by_source','rollback_count_by_source','error_streak_by_source','availability_error_by_source']:
    assert k in obj
print('OK')
PY`
Expected: OK

- [ ] **Step 3: Commit verification note**
```bash
git commit --allow-empty -m "chore(gate): pass S1 self-healing gate"
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
- add cron job with schedule from env (default 20m)
- update HEARTBEAT with job id and status

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
