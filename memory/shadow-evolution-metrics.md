# Shadow Evolution Metrics Guide

This document defines the operational metrics introduced for Shadow Evolution Pipeline V2 and how to interpret them safely.

## Metric definitions

### `shadow_decisions`
Total number of reconciliation decisions evaluated in shadow mode.

- Source: `memory/reconciliation-ledger.jsonl`
- Typical formula: count of records where decision path was evaluated by reconciliation logic.

### `shadow_accepted`
Count of shadow-evaluated decisions that met all promotion criteria and would be accepted by policy.

- This is a shadow signal first; acceptance does **not** imply immediate write-mode promotion unless `RECONCILIATION_WRITE_MODE=1`.

### `shadow_deferred`
Count of decisions deferred for triage/human review.

- Usually includes ambiguous, low-confidence, failed fact-check, or policy-incomplete candidates.

### `promoted_count`
Count of decisions actually promoted (write action performed).

- In pure shadow mode (`RECONCILIATION_WRITE_MODE=0`), this should remain `0`.
- Any non-zero value in shadow mode indicates a misconfiguration or policy breach and must be investigated.

### `triage_count`
Count of items routed to triage.

- Cross-check with `memory/triage-decisions.jsonl` append count.
- A sudden drop to zero can indicate triage bridge failure; a sudden spike can indicate upstream quality degradation.

### `causal_completeness_avg`
Average causal completeness score for processed candidates.

- Indicates evidence quality of incoming signals.
- Should be interpreted together with fact-check outcomes and deferred ratio.

## Interpretation guide

## 1) Safety posture checks (first pass)
- Verify `promoted_count == 0` when shadow mode is expected.
- Verify `shadow_deferred` is non-zero when uncertain/partial signals exist.
- Verify `triage_count` tracks deferred decisions that require human action.

## 2) Decision quality checks
- `shadow_accepted / shadow_decisions` too high + low evidence quality can indicate over-permissive thresholds.
- Low `causal_completeness_avg` + high `shadow_accepted` is a red flag.
- High `shadow_deferred` with stable quality may indicate strict but safe policy; tune only with replay evidence.

## 3) Stability checks across runs
- Compare daily/weekly drift in:
  - deferred ratio = `shadow_deferred / shadow_decisions`
  - acceptance ratio = `shadow_accepted / shadow_decisions`
  - triage ratio = `triage_count / shadow_decisions`
- Investigate abrupt changes together with `memory/model-threshold-changelog.md`.

## 4) Zero-false-positive guardrail expectations
- A candidate should only be promoted when all gate criteria pass.
- Fact-check failures should route to triage/deferred path.
- Unknown or partial evidence should increase deferred/triage, not promotion.

## Troubleshooting patterns

- `promoted_count > 0` while in shadow mode:
  - Confirm `RECONCILIATION_WRITE_MODE` value and runtime env source.
  - Inspect latest reconciliation ledger entries for incorrect gate application.

- `triage_count` unexpectedly low:
  - Check Mattermost delivery configuration.
  - Validate triage decision append-only writes.

- `causal_completeness_avg` degrades over time:
  - Inspect upstream signal sources and evidence payload richness.
  - Correlate with fact-check failures and threshold changes.
