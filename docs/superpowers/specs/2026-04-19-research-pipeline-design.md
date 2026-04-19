# Spec: Research Pipeline — Batch-First, Self-Evolving

**Date:** 2026-04-19  
**Status:** revised after review  
**Constraint order:** B (quality/confidence) → C (low cost) → D (self-healing) > A (coverage)  
**Latency:** batch-first, no real-time

---

## Context

`vault-ingest` runs 3x/day (10h, 14h, 20h BRT).  
`research-*` crons currently run every 10–20min, but GitHub/TLDV capture uses stubs and returns empty.

**Goal:** one logical research engine (shared `ResearchPipeline`) with deterministic batch processing, low cost, and self-healing.

---

## Design Decisions

### 1) Operational model: shared engine + 3 source crons (chosen)

There is **one pipeline engine** (`ResearchPipeline`) and **three source jobs** (trello/github/tldv) that call the same engine with different clients.

| Job | Engine | Source |
|---|---|---|
| `research-trello` | `ResearchPipeline(source="trello")` | Trello |
| `research-github` | `ResearchPipeline(source="github")` | GitHub |
| `research-tldv` | `ResearchPipeline(source="tldv")` | TLDV |
| `research-consolidation` | Consolidation orchestrator | all sources + compaction |

This resolves the previous contradiction between “single pipeline” and “3 crons”.

### 2) Dedup and SSOT

Each event key is `source:type:id[:action_id]`.
SSOT remains `state/identity-graph/state.json`.
Derived cache remains `.research/<source>/state.json`.

### 3) Operational mode (compatibility with prior write-mode specs)

Pipeline supports explicit mode flag:

- `PIPELINE_MODE=dedupe_only` (default)
- `PIPELINE_MODE=write_enabled`

Current rollout default is **`dedupe_only`** for safety.
Previous write-mode roadmap is preserved and gated behind `write_enabled` (plus existing breaker guards).

### 4) Source coverage contracts

#### Trello
- API source: board actions (`createCard`, `updateCard`, `moveListFromBoard`, member events).
- Cursor: `last_seen_at` (ISO UTC), sent as `since` to Trello API.

#### GitHub
- API source: PR events via `gh api`/Search API.
- Cursor: max(`merged_at`) per run.
- Replay safety: overlap window of 24h; dedupe by `event_key` prevents duplicates.

#### TLDV
- API source: Supabase `meetings` + `summaries` + `participants`.
- Cursor: `updated_at` high-watermark from `meetings`.
- Out-of-order handling: overlap window 24h on every run + idempotent dedupe by `event_key`.

### 5) Self-healing stages

| Stage | Trigger | Action |
|---|---|---|
| Monitoring | every batch | collect run outcomes + cost metrics |
| Auto-pause | threshold breach (`revert_rate`, `error_streak`) | pause source, keep audit trail |
| Recovery | cooldown elapsed + healthy run | resume source automatically |

### 6) Cost contract (explicit metrics)

Budget evaluation is based on **LLM token + API estimate** per run:

Required fields per run (minimum schema):
- `source`
- `token_used`
- `token_budget`
- `cost_usd_estimate`
- `api_calls`
- `api_cost_usd_estimate`

Policy:
- hard floor: minimum 4h between runs/source
- if 3 consecutive cycles exceed 80% of `token_budget`, move source to 6h cadence
- retries use exponential backoff (30s → 60s → 120s)

### 7) Identity resolution policy (YAGNI without architectural dead-end)

Cross-source identity resolution is **disabled by default**, but preserved by feature flag:
- `CROSS_SOURCE_IDENTITY_ENABLED=false` (default)

This keeps short-term cost/simplicity while preserving future quality path.

---

## Compatibility with previous specs

- Keeps SSOT and event-key model from research v1/v2.
- Keeps self-healing write path as optional mode (`write_enabled`), not removed.
- Keeps consolidation cron as daily governance point.
- Clarifies that current production rollout is conservative (`dedupe_only`).

---

## Naming convention

- **Code modules/files:** underscore (`research_trello_cron.py`)
- **Operational job names:** hyphen (`research-trello`)

Canonical mapping:
- `vault/crons/research_trello_cron.py` ↔ job `research-trello`
- `vault/crons/research_github_cron.py` ↔ job `research-github`
- `vault/crons/research_tldv_cron.py` ↔ job `research-tldv`

---

## File locations

| Component | Path |
|---|---|
| SSOT state | `state/identity-graph/state.json` |
| Source cache (derived) | `.research/<source>/state.json` |
| Audit log | `.research/<source>/audit.log` |
| Self-healing evidence | `.research/<source>/self_healing_evidence.jsonl` |
| Pipeline core | `vault/research/pipeline.py` |
| GitHub client | `vault/research/github_client.py` (new) |
| TLDV client | `vault/research/tldv_client.py` (new) |
| Trello client | `vault/research/trello_client.py` (existing) |
| Consolidation cron | `vault/crons/research_consolidation_cron.py` |
| Self-healing | `vault/research/self_healing.py` |

---

## Cron schedule (post-migration)

| Job | Schedule | Source |
|---|---|---|
| `research-trello` | `0 0,6,12,18 * * *` BRT | Trello |
| `research-github` | `0 0,6,12,18 * * *` BRT | GitHub |
| `research-tldv` | `0 0,6,12,18 * * *` BRT | TLDV |
| `research-consolidation` | `0 7 * * *` BRT | all + compaction |

Current 10–20min cadences must be replaced by 6h batch cadence.
