# Shadow Evolution Pipeline V2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a quality-first, auditável, evolutivo shadow-to-write pipeline with zero FP guardrails, Mattermost triage, Telegram override, and fact-checking via Context7 + official docs.

**Architecture:** Extend existing `curation_cron.py` flow with pluggable modules for scoring, dedup, tier classification, fact-checking, and confidence calibration. Keep shadow as default mode, promote only Tier A decisions passing all safety gates. Persist all decision traces as append-only audit artifacts.

**Tech Stack:** Python 3.12, pytest, JSONL artifacts, existing collectors/signal bus, Mattermost webhook/API, Telegram bot callbacks, Context7 API.

---

## File Structure Map

### New files
- `skills/memoria-consolidation/causal_scorer.py` — compute causal completeness + evidence cross-score
- `skills/memoria-consolidation/deduplicator.py` — semantic fingerprint + temporal dedup
- `skills/memoria-consolidation/tier_classifier.py` — Tier A/B/C classification
- `skills/memoria-consolidation/fact_checker.py` — Context7 + official docs verification
- `skills/memoria-consolidation/confidence_calibrator.py` — adaptive thresholds from feedback buffer
- `skills/memoria-consolidation/triage_bridge.py` — route triage decisions to Mattermost
- `skills/memoria-consolidation/mattermost_client.py` — API client helper
- `skills/memoria-consolidation/telegram_override_handler.py` — parse/apply override actions
- `tests/test_causal_scorer.py`
- `tests/test_deduplicator.py`
- `tests/test_tier_classifier.py`
- `tests/test_confidence_calibrator.py`
- `tests/test_signal_event_schema.py`
- `tests/test_ledger_entry_schema.py`
- `tests/test_triage_payload_schema.py`
- `tests/test_replay_10_real_cases.py`
- `tests/test_zero_fp_gate.py`
- `tests/test_shadow_to_triage_bridge.py`
- `tests/test_feedback_ingest_loop.py`
- `tests/fixtures/replay_r005_cases.json`

### Modified files
- `skills/memoria-consolidation/curation_cron.py` — integrate modules + gating logic
- `skills/memoria-consolidation/curation_cron_wrapper.sh` — ensure required env vars for new modules
- `skills/memoria-consolidation/learn_from_feedback.py` — expose structured feedback buffer for calibrator
- `memory/HEARTBEAT.md` or generated heartbeat pipeline output — add new metrics visibility

### Runtime artifacts (append-only)
- `memory/reconciliation-ledger.jsonl`
- `memory/triage-decisions.jsonl`
- `memory/promotion-events.jsonl`
- `memory/fact-check-log.jsonl`
- `memory/model-threshold-changelog.md`

---

## Task 1: Baseline safety net (TDD scaffolding + replay fixtures)

**Files:**
- Create: `tests/fixtures/replay_r005_cases.json`
- Create: `tests/test_replay_10_real_cases.py`
- Create: `tests/test_zero_fp_gate.py`

- [ ] **Step 1: Build fixture with current 10 deferred R005 cases**
- [ ] **Step 2: Write failing replay test asserting all 10 remain deferred under strict gate**
- [ ] **Step 3: Write failing zero-FP safety test (`missing criteria => never promote`)**
- [ ] **Step 4: Run tests and capture expected failures**
  - Run: `pytest tests/test_replay_10_real_cases.py tests/test_zero_fp_gate.py -v`
  - Expected: FAIL (modules not implemented yet)
- [ ] **Step 5: Commit**
  - `git commit -m "test: add replay fixture and zero-fp gate failing tests"`

---

## Task 2: Implement causal scorer (quality first)

**Files:**
- Create: `skills/memoria-consolidation/causal_scorer.py`
- Create: `tests/test_causal_scorer.py`

- [ ] **Step 1: Write failing unit tests for scoring formula and edge-cases**
- [ ] **Step 2: Run test to verify failure**
  - Run: `pytest tests/test_causal_scorer.py -v`
- [ ] **Step 3: Implement minimal scorer API**
- [ ] **Step 4: Make tests pass**
  - Run: `pytest tests/test_causal_scorer.py -v`
- [ ] **Step 5: Commit**
  - `git commit -m "feat: add causal scorer with quality-first thresholds"`

---

## Task 3: Implement deduplicator (noise reduction)

**Files:**
- Create: `skills/memoria-consolidation/deduplicator.py`
- Create: `tests/test_deduplicator.py`

- [ ] **Step 1: Write failing tests for fingerprint collision-safe dedup and 7-day window behavior**
- [ ] **Step 2: Run tests and verify fail**
- [ ] **Step 3: Implement dedup logic**
- [ ] **Step 4: Run tests and verify pass**
- [ ] **Step 5: Commit**
  - `git commit -m "feat: add semantic deduplicator with temporal window"`

---

## Task 4: Tier classifier + policy gate

**Files:**
- Create: `skills/memoria-consolidation/tier_classifier.py`
- Create: `tests/test_tier_classifier.py`
- Modify: `tests/test_zero_fp_gate.py`

- [ ] **Step 1: Write failing tests for Tier A/B/C classification**
- [ ] **Step 2: Write failing test for policy gate requiring all 5 criteria**
- [ ] **Step 3: Implement classifier and gate helper**
- [ ] **Step 4: Run tests and verify pass**
- [ ] **Step 5: Commit**
  - `git commit -m "feat: add risk-tier classifier and strict promotion gate"`

---

## Task 5: Fact-checking pipeline (Context7 + official docs)

**Files:**
- Create: `skills/memoria-consolidation/fact_checker.py`
- Create: `tests/test_fact_checker.py`
- Modify: `skills/memoria-consolidation/curation_cron_wrapper.sh`

- [ ] **Step 1: Write failing tests for fact-check success/failure and fallback behavior**
- [ ] **Step 2: Add env precondition test for `CONTEXT7_API_KEY` handling**
- [ ] **Step 3: Implement fact checker client abstraction**
- [ ] **Step 4: Implement `fact_check_log.jsonl` append-only writer**
- [ ] **Step 5: Run tests and verify pass**
  - Run: `pytest tests/test_fact_checker.py -v`
- [ ] **Step 6: Commit**
  - `git commit -m "feat: add Context7 + official-docs fact-check gate"`

---

## Task 6: Mattermost triage bridge + Telegram override

**Files:**
- Create: `skills/memoria-consolidation/mattermost_client.py`
- Create: `skills/memoria-consolidation/triage_bridge.py`
- Create: `skills/memoria-consolidation/telegram_override_handler.py`
- Create: `tests/test_shadow_to_triage_bridge.py`

- [ ] **Step 1: Write failing integration test for triage payload emission to Mattermost**
- [ ] **Step 2: Write failing test for Telegram override parsing (`hold/promote` with reason)**
- [ ] **Step 3: Implement Mattermost client and bridge**
- [ ] **Step 4: Implement override handler with audit logging**
- [ ] **Step 5: Run integration tests and verify pass**
- [ ] **Step 6: Commit**
  - `git commit -m "feat: add mattermost triage bridge and telegram override handler"`

---

## Task 7: Confidence calibrator + feedback loop

**Files:**
- Create: `skills/memoria-consolidation/confidence_calibrator.py`
- Create: `tests/test_confidence_calibrator.py`
- Create: `tests/test_feedback_ingest_loop.py`
- Modify: `skills/memoria-consolidation/learn_from_feedback.py`

- [ ] **Step 1: Write failing tests for threshold adjustment constraints (max ±0.05/cycle)**
- [ ] **Step 2: Write failing tests for minimum sample size (>=20) rule**
- [ ] **Step 3: Implement calibrator and changelog writer**
- [ ] **Step 4: Integrate feedback buffer ingestion**
- [ ] **Step 5: Run tests and verify pass**
- [ ] **Step 6: Commit**
  - `git commit -m "feat: add confidence calibrator with guarded adaptation"`

---

## Task 8: Integrate modules in curation_cron.py

**Files:**
- Modify: `skills/memoria-consolidation/curation_cron.py`
- Create: `tests/test_signal_event_schema.py`
- Create: `tests/test_ledger_entry_schema.py`
- Create: `tests/test_triage_payload_schema.py`

- [ ] **Step 1: Write failing contract tests for event/ledger/triage payload schemas**
- [ ] **Step 2: Implement integration points in cron orchestration**
- [ ] **Step 3: Ensure append-only artifact writes**
- [ ] **Step 4: Run full targeted test suite**
  - Run: `pytest tests/test_*scorer.py tests/test_*dedup*.py tests/test_*tier*.py tests/test_*schema*.py tests/test_replay_10_real_cases.py tests/test_zero_fp_gate.py tests/test_shadow_to_triage_bridge.py tests/test_feedback_ingest_loop.py -v`
- [ ] **Step 5: Commit**
  - `git commit -m "feat: integrate shadow evolution modules into curation cron"`

---

## Task 9: End-to-end dry-run validation

**Files:**
- Modify (if needed): `skills/memoria-consolidation/curation_cron_wrapper.sh`
- Produce runtime: `memory/*.jsonl`, `memory/reconciliation-report.md`

- [ ] **Step 1: Run curation cron in shadow mode with new pipeline enabled**
  - Run: `bash skills/memoria-consolidation/curation_cron_wrapper.sh`
- [ ] **Step 2: Validate generated artifacts are complete and append-only**
- [ ] **Step 3: Verify no auto-promotion occurs unless all 5 criteria pass**
- [ ] **Step 4: Validate Mattermost triage payload emission and Telegram summary format**
- [ ] **Step 5: Commit any fixes**
  - `git commit -m "test: validate end-to-end shadow evolution dry-run"`

---

## Task 10: Observability and ops handoff

**Files:**
- Create/Modify: `docs/memory-manual.md` (or dedicated ops doc)
- Optional: `HEARTBEAT.md` sections for metrics

- [ ] **Step 1: Document new metrics and interpretation guide**
- [ ] **Step 2: Document rollback runbook for false-positive prevention**
- [ ] **Step 3: Document env requirements (`CONTEXT7_API_KEY`, Mattermost vars)**
- [ ] **Step 4: Run full regression tests**
  - Run: `pytest tests -v`
- [ ] **Step 5: Commit**
  - `git commit -m "docs: add shadow evolution ops runbook and observability guide"`

---

## Verification Checklist (before merge)

- [ ] Replay of 10 historical R005 cases still yields zero false positives
- [ ] Promotion gate enforces all 5 criteria (hard requirement)
- [ ] Fact-check failures route to triage (never auto-promote)
- [ ] Triage events always produce auditable trail
- [ ] Telegram override requires explicit reason and is logged
- [ ] All new artifacts are append-only
- [ ] Test suite green (`pytest tests -v`)

---

## Suggested Commit Cadence

1. tests baseline (replay + safety)
2. scorer
3. dedup
4. tier gate
5. fact-check
6. triage bridge + override
7. calibrator
8. integration + schemas
9. e2e dry-run
10. docs/runbook
