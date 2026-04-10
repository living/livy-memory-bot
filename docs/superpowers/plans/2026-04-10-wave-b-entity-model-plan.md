# Wave B — Entity Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materializar entidades canônicas `person`, `project`, `repo` no vault com resolução de identidade semi-automática, observabilidade e correlação completa.

**Architecture:** Ingest de TLDV + GitHub alimenta writers por entidade. Resolver mantém cache append-only e merge candidates. Contrato canônico exige `source_keys`, `sources`, `lineage`, `relationships`, `linked_from`.

**Tech Stack:** Python 3.12, pytest, YAML frontmatter, JSONL append-only, GitHub REST API, TLDV pipeline.

---

## File Structure Map

### Create
- `vault/domain/person_entity.py`
- `vault/domain/project_entity.py`
- `vault/domain/repo_entity.py`
- `vault/identity/resolver.py`
- `vault/ingest/person_ingest.py`
- `vault/ingest/project_ingest.py`
- `vault/ingest/repo_ingest.py`
- `vault/ingest/github_allowlist.py`
- `vault/backlinks.py`
- `vault/quality/entity_lint.py`
- `vault/quality/entity_quality.py`
- `vault/tests/test_domain_contract.py`
- `vault/tests/test_identity_resolution.py`
- `vault/tests/test_relation_generation.py`
- `vault/tests/test_window_filter.py`
- `vault/tests/test_traceability_fields.py`
- `vault/tests/test_github_scope_allowlist.py`

### Modify
- `vault/quality/domain_lint.py`
- `vault/quality/quality_review.py`
- `memory/vault/index.md`
- `CLAUDE.md`

---

## Task 1: Domain Contract Tests (RED baseline)

**Files:**
- Create: `vault/tests/test_domain_contract.py`

- [ ] **Step 1: Write failing tests for Person/Project/Repo required fields**

```python
# Person contract
def test_person_contract_required_fields():
    required = [
        "id_canonical", "slug", "type", "display_name", "source_keys", "sources",
        "first_seen_at", "last_seen_at", "confidence", "lineage", "relationships", "linked_from"
    ]
    ...

# Project contract
def test_project_contract_required_fields():
    required = [
        "id_canonical", "slug", "type", "display_name", "status", "aliases",
        "source_keys", "sources", "first_seen_at", "last_seen_at", "confidence", "lineage", "relationships", "linked_from"
    ]
    ...

# Repo contract
def test_repo_contract_required_fields():
    required = [
        "id_canonical", "slug", "type", "name", "owner", "archived", "project_ref",
        "source_keys", "sources", "first_seen_at", "last_seen_at", "confidence", "lineage", "relationships", "linked_from"
    ]
    ...
```

- [ ] **Step 2: Run test to confirm RED**

Run:
```bash
python3 -m pytest vault/tests/test_domain_contract.py -v --tb=short
```
Expected: FAIL (modules not implemented)

- [ ] **Step 3: Commit RED tests**

```bash
git add vault/tests/test_domain_contract.py
git commit -m "test(vault): add Wave B domain contract baseline tests"
```

---

## Task 2: Implement Domain Entities (Person/Project/Repo)

**Files:**
- Create: `vault/domain/person_entity.py`
- Create: `vault/domain/project_entity.py`
- Create: `vault/domain/repo_entity.py`

- [ ] **Step 1: Implement PersonEntity with spec-aligned fields**

Required fields in `to_frontmatter()`:
- `display_name`
- `github_login`
- `source_keys`
- `sources`
- `lineage` (`run_id`, `source_keys`, `transformed_at`, `mapper_version`, `actor`)
- `relationships`, `linked_from`

- [ ] **Step 2: Implement ProjectEntity with status/aliases/confidence**
- [ ] **Step 3: Implement RepoEntity with archived/project_ref/merged_at/source_keys**

- [ ] **Step 4: Run contract tests (GREEN)**

```bash
python3 -m pytest vault/tests/test_domain_contract.py -v --tb=short
```

- [ ] **Step 5: Commit**

```bash
git add vault/domain/person_entity.py vault/domain/project_entity.py vault/domain/repo_entity.py
git commit -m "feat(vault/domain): add Wave B canonical entity types"
```

---

## Task 3: Identity Resolution (semi-auto policy)

**Files:**
- Create: `vault/identity/resolver.py`
- Create: `vault/tests/test_identity_resolution.py`
- Create: `memory/vault/.resolution-cache.jsonl`
- Create: `memory/vault/.merge-candidates.jsonl`

- [ ] **Step 1: Write failing tests for scoring + merge policy**

Tests must assert:
- similarity >= 0.85 alone is **not enough**
- auto-merge requires `>=2 source_keys`
- 0.60–0.84 goes to merge candidates

- [ ] **Step 2: Run tests RED**

```bash
python3 -m pytest vault/tests/test_identity_resolution.py -v --tb=short
```

- [ ] **Step 3: Implement resolver**

- append-only resolution cache
- merge candidates log
- semi-auto policy guardrail

- [ ] **Step 4: Run tests GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/identity/resolver.py vault/tests/test_identity_resolution.py memory/vault/.resolution-cache.jsonl memory/vault/.merge-candidates.jsonl
git commit -m "feat(vault/identity): add semi-auto resolver with source-key guardrails"
```

---

## Task 4: Ingest Pipelines with boundaries

**Files:**
- Create: `vault/ingest/person_ingest.py`
- Create: `vault/ingest/project_ingest.py`
- Create: `vault/ingest/repo_ingest.py`
- Create: `vault/ingest/github_allowlist.py`
- Create: `vault/tests/test_window_filter.py`
- Create: `vault/tests/test_github_scope_allowlist.py`

- [ ] **Step 1: Write failing tests for TLDV 30-day default window**
- [ ] **Step 2: Write failing tests for GitHub allowlist boundaries**
- [ ] **Step 3: Run tests RED**

```bash
python3 -m pytest vault/tests/test_window_filter.py vault/tests/test_github_scope_allowlist.py -v --tb=short
```

- [ ] **Step 4: Implement GitHub scope enforcement**

Must enforce in order:
1. `org_allowlist`
2. `repo_allowlist` (if non-empty)
3. `repo_denylist`

- [ ] **Step 5: Implement TLDV person/project ingest with default `days=30`**
- [ ] **Step 6: Run tests GREEN**
- [ ] **Step 7: Commit**

```bash
git add vault/ingest/person_ingest.py vault/ingest/project_ingest.py vault/ingest/repo_ingest.py vault/ingest/github_allowlist.py vault/tests/test_window_filter.py vault/tests/test_github_scope_allowlist.py
git commit -m "feat(vault/ingest): add Wave B ingest with GitHub scope enforcement"
```

---

## Task 5: Relationships + Backlinks

**Files:**
- Create: `vault/backlinks.py`
- Create: `vault/tests/test_relation_generation.py`
- Create: `vault/tests/test_traceability_fields.py`

- [ ] **Step 1: Write failing tests for relationship generation schema**

Required shape:
```yaml
relationships:
  - to_id: project:tldv:bat-conectabot
    role: participant
    since: 2026-04-01
    until:
    source_ref: tldv:meeting:123
    confidence: medium
```

And linked_from shape:
```yaml
linked_from:
  - entity_ref: decision:2026-04-07-pr-1
    role: mentions
    source_ref: tldv:meeting:123
    confidence: medium
```

- [ ] **Step 2: Run tests RED**

```bash
python3 -m pytest vault/tests/test_relation_generation.py vault/tests/test_traceability_fields.py -v --tb=short
```

- [ ] **Step 3: Implement backlinks and traceability generation**
- [ ] **Step 4: Run tests GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/backlinks.py vault/tests/test_relation_generation.py vault/tests/test_traceability_fields.py
git commit -m "feat(vault): add relationship generation and backlinks model"
```

---

## Task 6: Entity quality and observability

**Files:**
- Create: `vault/quality/entity_lint.py`
- Create: `vault/quality/entity_quality.py`
- Modify: `vault/quality/domain_lint.py`
- Modify: `vault/quality/quality_review.py`

- [ ] **Step 1: Add failing tests for entity lint and quality stats**
- [ ] **Step 2: Run tests RED**

```bash
python3 -m pytest vault/tests/test_domain_contract.py -k "lint or quality" -v --tb=short
```

- [ ] **Step 3: Implement**

Metrics required:
- `persons_total`, `projects_total`, `repos_total`
- `stale_rate`, `orphan_rate`, `merge_candidate_count`
- `high_confidence_without_multi_source`

- [ ] **Step 4: Run tests GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/quality/entity_lint.py vault/quality/entity_quality.py vault/quality/domain_lint.py vault/quality/quality_review.py
git commit -m "feat(vault/quality): add Wave B entity lint and quality metrics"
```

---

## Task 7: Docs + final verification + PR

**Files:**
- Modify: `memory/vault/index.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Update index with person/project/repo sections**
- [ ] **Step 2: Update CLAUDE.md runbook for Wave B ingest and checks**
- [ ] **Step 3: Run full regression**

```bash
python3 -m pytest vault/tests/ -q --tb=no
python3 -m vault.pipeline --dry-run -v
```

- [ ] **Step 4: Generate final quality artifacts and commit**

```bash
git add memory/vault/index.md CLAUDE.md memory/vault/quality-review memory/vault/lint-reports
git commit -m "docs(vault): finalize Wave B runbook and verification artifacts"
```

- [ ] **Step 5: Push branch + open PR**

```bash
git push origin feature/wave-b-entity-model
gh pr create --repo living/livy-memory-bot --base master --head feature/wave-b-entity-model --draft --title "feat(vault): Wave B entity model (person/project/repo)" --body "Wave B complete: entities + resolver + ingest + relationships + quality."
```

---

## Test Matrix (must pass)

| Layer | Command | Pass Criteria |
|---|---|---|
| Domain contract | `pytest vault/tests/test_domain_contract.py -v` | green |
| Identity resolution | `pytest vault/tests/test_identity_resolution.py -v` | green |
| Relationships | `pytest vault/tests/test_relation_generation.py -v` | green |
| Window filter | `pytest vault/tests/test_window_filter.py -v` | green |
| Traceability | `pytest vault/tests/test_traceability_fields.py -v` | green |
| GitHub allowlist | `pytest vault/tests/test_github_scope_allowlist.py -v` | green |
| Full regression | `pytest vault/tests/ -q --tb=no` | 0 failures |

---

## Risks & Mitigations

1. **False positive merges** → auto-merge requires similarity + multi-source evidence.
2. **GitHub scope leak** → hard allowlist enforcement before ingest.
3. **Stale entity sprawl** → stale/orphan metrics in lint and quality report.
4. **Traceability gaps** → lineage required in all entity contracts.
