# Wave B — Entity Model Design (Person, Project, Repo)

**Scope choices (approved):**
- Coverage: **complete**
- Sources: **TLDV + GitHub only**
- Canonical strategy: **hybrid** (human slug filename + immutable `id_canonical`)
- Automation: **semi-auto** (auto-merge high confidence, review ambiguous)

---

## 1) Canonical entity contracts

All entity pages MUST include:
- `id_canonical`
- `slug`
- `type`
- `source_keys` (string array)
- `sources` (canonical evidence records)
- `first_seen_at`
- `last_seen_at`
- `confidence`
- `lineage` block (required)

### 1.1 Person
Required/important fields:
- `display_name` (preferred over `name`)
- `github_login` (optional)
- `aliases` (array)

Example:
```yaml
id_canonical: person:tldv:robert-abc123
slug: robert
type: person
display_name: Robert Silva
github_login: robert-git
aliases: ["robert@livingnet.com.br"]
source_keys: ["tldv:participant:robert-abc123", "github:user:robert-git"]
sources:
  - source_type: tldv_api
    source_ref: tldv:participant:robert-abc123
    retrieved_at: 2026-04-10T00:00:00Z
    mapper_version: wave-b-person-v1
first_seen_at: 2026-03-01T00:00:00Z
last_seen_at: 2026-04-10T00:00:00Z
confidence: medium
lineage:
  run_id: wave-b-20260410
  source_keys: ["tldv:participant:robert-abc123"]
  transformed_at: 2026-04-10T00:00:00Z
  mapper_version: wave-b-person-v1
  actor: livy-agent
relationships: []
linked_from: []
```

### 1.2 Project
Required additional fields:
- `status` (optional)
- `aliases` (optional array)

### 1.3 Repo
Required additional fields:
- `owner`
- `archived` (bool)
- `project_ref` (optional)
- `merged_at` (optional for PR-derived context)

---

## 2) Relationship and backlink model

Every entity supports:
- `relationships[]` (typed edges)
- `linked_from[]` (reverse pointers)

Relationship item shape:
```yaml
relationships:
  - to_id: project:tldv:bat-conectabot
    role: participant
    since: 2026-04-01
    until:
    source_ref: tldv:meeting:123
    confidence: medium
```

Linked-from item shape:
```yaml
linked_from:
  - entity_ref: decision:2026-04-07-pr-1
    role: mentions
    source_ref: tldv:meeting:123
    confidence: medium
```

---

## 3) Identity resolution policy

Scoring thresholds:
- `>= 0.85` candidate for auto-merge
- `0.60 - 0.84` ambiguous (manual review)
- `< 0.60` new entity

**Guardrail:** auto-merge requires both:
1. similarity `>= 0.85`
2. resulting canonical has `>= 2 source_keys`

Otherwise, create merge candidate in `.merge-candidates.jsonl`.

---

## 4) Ingest boundaries and security

GitHub ingestion MUST enforce scope boundaries before API processing:
- `org_allowlist`
- `repo_allowlist`
- `repo_denylist`

No repository outside allowlist enters the pipeline.

TLDV ingest default lookback window: **30 days** (configurable).

---

## 5) Observability / quality

Entity lint checks:
- required fields present
- lineage completeness
- relationship schema validity
- orphan/stale flags

Quality metrics include:
- persons/projects/repos totals
- stale_rate
- orphan_rate
- merge_candidate_count
- high_confidence_without_multi_source (must be 0)

---

## 6) Required tests for Wave B

Minimum suite:
- `test_domain_contract.py`
- `test_identity_resolution.py`
- `test_relation_generation.py`
- `test_window_filter.py`
- `test_traceability_fields.py`
- `test_github_scope_allowlist.py`

(Additional per-module tests are welcome, but these contracts are mandatory.)
