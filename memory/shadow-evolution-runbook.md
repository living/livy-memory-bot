# Shadow Evolution Pipeline V2 — Operations Runbook

## Modes of operation

### Shadow mode (default, safe)
```
RECONCILIATION_WRITE_MODE=0
```
All reconciliation decisions are evaluated but **no writes occur**. Decisions are logged to `memory/reconciliation-ledger.jsonl` for audit and review. Use this mode during initial deployment, after threshold changes, or whenever confidence is low.

### Write mode (production promotion)
```
RECONCILIATION_WRITE_MODE=1
```
Decisions that pass all safety gates are promoted immediately. Use only after shadow mode validation confirms zero false positives over a representative sample.

## How to run in shadow mode

```bash
# Standard invocation
bash skills/memoria-consolidation/curation_cron_wrapper.sh

# Explicit shadow mode (preferred for validation runs)
RECONCILIATION_WRITE_MODE=0 bash skills/memoria-consolidation/curation_cron_wrapper.sh
```

Expected output:
- `memory/reconciliation-ledger.jsonl` receives new entries (append-only).
- `memory/triage-decisions.jsonl` receives triage routing decisions.
- `memory/signal-events.jsonl` accumulates signal events.
- **No** direct memory writes occur (promotions are deferred).

## How to promote to write mode

### Pre-requisites
- Shadow mode has been running for at least 3–5 cycles with no anomalous `promoted_count` spikes.
- `promoted_count` in shadow mode stays at `0` (validation).
- `shadow_deferred` ratio is stable and makes sense for your signal volume.

### Steps
1. Inspect recent reconciliation ledger entries:
```bash
tail -20 memory/reconciliation-ledger.jsonl | jq .
```
Confirm entries show `status: deferred` or `status: shadow` for non-trivial signals.

2. Enable write mode:
```bash
export RECONCILIATION_WRITE_MODE=1
bash skills/memoria-consolidation/curation_cron_wrapper.sh
```

3. Monitor the first cycle closely:
```bash
# Watch promotion events
tail -f memory/promotion-events.jsonl
# Watch ledger
tail -f memory/reconciliation-ledger.jsonl
```

4. Verify `promoted_count` appears only for entries where all 5 gate criteria pass.

## Rollback procedure — immediate response to false positives

If a false positive promotion is detected:

### Step 1 — Stop write mode immediately
```bash
export RECONCILIATION_WRITE_MODE=0
```

### Step 2 — Identify affected entries
```bash
# Find recent promotion events
grep "promoted" memory/promotion-events.jsonl | tail -20 | jq .
```

### Step 3 — Inspect decision context
```bash
# Cross-reference ledger entries
grep "<topic-id>" memory/reconciliation-ledger.jsonl | tail -10 | jq .
```

### Step 4 — Record false positive in feedback
```bash
# Log via feedback mechanism for calibrator to adapt
echo '{"topic":"<topic>","action":"promote","correct_action":"defer","reason":"<description>","timestamp":"<iso>"}' >> memory/feedback-log.jsonl
```

### Step 5 — Trigger recalibration (optional, guided)
```bash
# Run feedback ingestion to update thresholds
python3 skills/memoria-consolidation/learn_from_feedback.py
```

### Step 6 — Review threshold changelog
```bash
cat memory/model-threshold-changelog.md
```

## How to inspect reconciliation-ledger.jsonl

```bash
# Count total entries
wc -l memory/reconciliation-ledger.jsonl

# View recent decisions
tail -20 memory/reconciliation-ledger.jsonl | jq .

# Filter by rule
grep '"rule":"R005"' memory/reconciliation-ledger.jsonl | jq .

# Filter by status
grep '"status":"deferred"' memory/reconciliation-ledger.jsonl | jq .

# Summarize by rule
cat memory/reconciliation-ledger.jsonl | jq -r '.rule' | sort | uniq -c | sort -rn
```

## How to inspect triage-decisions.jsonl

```bash
# Count triage decisions
wc -l memory/triage-decisions.jsonl

# View recent triage routing
tail -30 memory/triage-decisions.jsonl | jq .

# Show pending triage items
grep '"status":"pending"' memory/triage-decisions.jsonl | jq .

# Summarize by triage action
cat memory/triage-decisions.jsonl | jq -r '.triage_action // .action' | sort | uniq -c
```

## How to interpret model-threshold-changelog.md

```bash
cat memory/model-threshold-changelog.md
```

Look for:
- **Direction of change**: threshold tightening (+), loosening (-)
- **Sample size basis**: confirm >= 20 feedback samples per calibration cycle
- **Max drift cap**: no single cycle should change thresholds by more than ±0.05
- **Date of last calibration**: if older than 7 days, recalibration may be stale
- **Reason field**: explains the business logic behind the threshold change

A healthy changelog shows gradual, bounded changes. Sudden large jumps indicate potential miscalibration or corrupted feedback data.

## Emergency contacts / escalation

- Telegram override: send a message to the configured Telegram bot with the override syntax:
  - `hold <topic-id> <reason>` — prevent promotion
  - `promote <topic-id> <reason>` — force promotion with audit trail
- Mattermost: triage channel receives alerts for all deferred decisions

## Safety checklist before switching to write mode

- [ ] Shadow mode ran for ≥ 3 cycles
- [ ] `promoted_count` was zero in every shadow cycle
- [ ] `shadow_deferred / shadow_decisions` ratio is stable
- [ ] Fact-check failures correctly route to triage
- [ ] `memory/model-threshold-changelog.md` shows no anomalous drift
- [ ] All tests pass: `pytest tests -v`
