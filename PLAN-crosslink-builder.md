# Implementation Plan: Cross-Linking Pipeline

> Branch: `feature/crosslink-builder`  
> TDD: Red → Green → Refactor for every task  
> Estimated total: 16 tasks × ~45 min = ~12 hours

---

## Architecture Overview

```
Trello Cards ──→ card-person, card-project links
GitHub PRs   ──→ pr-person, pr-project links
                      ↓
              Person entities (enriched with cards/PRs)
              Project entities (enriched with cards/PRs/persons)
                      ↓
              Meeting entities (get context transitively via projects)
```

**Key principle:** Cards and PRs link to Persons and Projects. Meetings get context transitively through projects — NOT by date proximity.

---

## API Reference (Verified)

### Trello API — Member Info
- **GET** `https://api.trello.com/1/members/{id}?key={key}&token={token}`
- **Response shape:**
  ```json
  {
    "id": "5a6b...",
    "fullName": "Lincoln Quinan Junior",
    "username": "lincolnq",
    "email": "lincoln@livingnet.com.br"
  }
  ```
- Already used in `card_ingest.py` via `members=true` param on board cards endpoint, which returns `members[]` with `{id, fullName, username}`.

### Trello API — Card Members
- Cards endpoint already returns `idMembers` (list of member IDs) and `members` (with `fullName`, `username`).
- No additional API call needed for member resolution from cards.

### GitHub API — PR Author
- **GET** `https://api.github.com/repos/{owner}/{repo}/pulls/{number}`
- Already used in `enrich_github.py`. Response includes:
  ```json
  {
    "user": { "login": "lincolnq", "id": 12345 },
    "merged_by": { "login": "robertu" },
    "title": "...",
    "html_url": "..."
  }
  ```
- The `user.login` field is the PR author.

### GitHub API — Repo PRs (for batch)
- **GET** `https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=100`
- Returns list of PR objects with same shape.

---

## Task 1: Setup — Branch, Directory Structure, Empty Modules

**Files to create:**
- `vault/ingest/crosslink_builder.py` (empty, just docstring)
- `vault/tests/test_crosslink_builder.py` (empty test file)
- `memory/vault/entities/prs/.gitkeep`
- `memory/vault/relationships/.gitkeep` (already exists)

**Files to modify:** None yet.

**Acceptance criteria:**
- Branch `feature/crosslink-builder` created from current master
- All empty files exist
- `python3 -m pytest vault/tests/ -q` passes (no regressions)

**Dependencies:** None.

---

## Task 2: Mapping Configs — YAML Schemas, Loader, Tests

**Files to create:**
- `memory/vault/schema/trello-member-map.yaml`
- `memory/vault/schema/repo-project-map.yaml`
- `memory/vault/schema/board-project-map.yaml`
- `vault/ingest/mapping_loader.py`

**Files to modify:**
- `vault/tests/test_crosslink_builder.py` (or new `vault/tests/test_mapping_loader.py`)

**YAML schemas:**

`trello-member-map.yaml`:
```yaml
# Trello member ID → person name (for cross-linking)
# Auto-populated by member resolution, manually curated
members:
  "5a6b7c8d": "Lincoln Quinan Junior"
  "9e0f1a2b": "Robert Urech"
```

`repo-project-map.yaml`:
```yaml
# GitHub repo (owner/name) → project name
repos:
  "living/AbsRio-ApiCRM": "BAT/Kaba"
  "living/livy-bat-jobs": "BAT/Kaba"
  "living/livy-delphos-jobs": "Delphos"
  "living/livy-tldv-jobs": "TLDV"
  "living/livy-forge-platform": "Forge"
  "living/livy-memory-bot": "Livy Memory"
```

`board-project-map.yaml`:
```yaml
# Trello board ID → project name
boards:
  "abc123": "BAT/Kaba"
  "def456": "Delphos"
```

**`mapping_loader.py` functions:**
```python
def load_trello_member_map(schema_dir: Path) -> dict[str, str]
def load_repo_project_map(schema_dir: Path) -> dict[str, str]
def load_board_project_map(schema_dir: Path) -> dict[str, str]
def resolve_trello_member_to_person(member_id: str, member_map: dict[str, str], vault_root: Path) -> str | None
def resolve_repo_to_project(repo_full_name: str, repo_map: dict[str, str]) -> str | None
def resolve_board_to_project(board_id: str, board_map: dict[str, str]) -> str | None
```

**Test cases:**
1. `test_load_trello_member_map_valid` — loads YAML, returns dict
2. `test_load_trello_member_map_missing_file` — returns empty dict
3. `test_load_trello_member_map_empty` — returns empty dict
4. `test_resolve_trello_member_found` — maps known ID to person name
5. `test_resolve_trello_member_unmapped` — returns None for unknown ID
6. `test_resolve_repo_to_project_found` — maps repo to project
7. `test_resolve_repo_to_project_unmapped` — returns None
8. `test_resolve_board_to_project_found` — maps board to project
9. `test_resolve_board_to_project_unmapped` — returns None
10. `test_resolve_trello_member_fuzzy_match` — uses person vault files for fuzzy name matching when ID not in map

**Acceptance criteria:**
- All tests pass
- Loader handles missing/empty files gracefully
- Fuzzy matching works via person entity files

**Dependencies:** Task 1.

---

## Task 3: Trello Member Resolution — Auto-Populate Mapping

**Files to create:** None new.

**Files to modify:**
- `vault/ingest/crosslink_builder.py` — add `resolve_card_members()`
- `vault/tests/test_crosslink_builder.py`

**What it does:**
- Takes a card entity (already has `idMembers` and `members` from `card_ingest.extract_assignees()`)
- For each member: checks `trello-member-map.yaml` → if not found, tries fuzzy match against person entity files → if still not found, calls Trello API to get fullName and creates draft person
- Auto-populates the mapping YAML with new entries

**Function signatures:**
```python
def resolve_card_members(
    card_entity: dict,
    member_map: dict[str, str],
    vault_root: Path,
    trello_api_key: str | None = None,
    trello_token: str | None = None,
) -> list[str]  # list of person names/wiki-links
```

**Test cases:**
1. `test_resolve_card_members_all_mapped` — all member IDs in map
2. `test_resolve_card_members_none_mapped` — no IDs in map, fuzzy match via vault
3. `test_resolve_card_members_partial` — some mapped, some not
4. `test_resolve_card_members_no_members` — empty idMembers
5. `test_resolve_card_members_creates_draft_person` — unmapped member creates draft person entity
6. `test_resolve_card_members_auto_populates_map` — mapping YAML gets new entries

**Acceptance criteria:**
- Members resolved to person names
- Mapping YAML auto-populated
- Draft persons created for unknown members

**Dependencies:** Task 2.

---

## Task 4: GitHub PR Author Resolution

**Files to modify:**
- `vault/ingest/crosslink_builder.py` — add `resolve_pr_author()`, `fetch_prs_for_repos()`
- `vault/tests/test_crosslink_builder.py`

**What it does:**
- Given PR data (from enrichment_context), extract author login
- Map login to person via: (1) `github_login` field in person frontmatter, (2) fuzzy name match, (3) create draft person
- Also fetches PRs from GitHub API for configured repos

**Function signatures:**
```python
def resolve_pr_author(
    pr_data: dict,
    vault_root: Path,
) -> str | None  # person name

def fetch_prs_for_repos(
    repos: list[str],
    github_token: str | None = None,
    days: int = 30,
) -> list[dict]
```

**Test cases:**
1. `test_resolve_pr_author_by_github_login` — person with matching `github_login` found
2. `test_resolve_pr_author_unmapped` — login not in any person, returns None (or creates draft)
3. `test_resolve_pr_author_creates_draft` — creates draft person entity
4. `test_fetch_prs_for_repos` — mocked API call returns PR list
5. `test_fetch_prs_for_repos_empty` — no repos configured

**API calls:**
- `GET https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page=100&sort=updated&direction=desc`
- Response: list of PR objects with `user.login`, `title`, `html_url`, `merged_at`, `created_at`

**Acceptance criteria:**
- PR author resolved to person name
- Draft persons created when needed
- API calls mocked in tests

**Dependencies:** Task 2.

---

## Task 5: PR Entity Writer — `upsert_pr()`

**Files to modify:**
- `vault/ingest/entity_writer.py` — add `upsert_pr()`
- `vault/tests/test_crosslink_builder.py` (or `test_entity_writer.py`)

**PR entity shape:**
```markdown
---
entity: "Fix login redirect"
type: pr
id_canonical: "pr:living/AbsRio-ApiCRM:42"
pr_id_source: 42
repo: "living/AbsRio-ApiCRM"
author: "lincolnq"
project_ref: "BAT/Kaba"
confidence: medium
source_keys:
  - github:living/AbsRio-ApiCRM:42
---

# Fix login redirect

> [!info] living/AbsRio-ApiCRM · PR #42

## Dados
- **Repo:** living/AbsRio-ApiCRM
- **Autor:** [[Lincoln Quinan Junior]]
- **Projeto:** [[BAT/Kaba]]
- **URL:** https://github.com/living/AbsRio-ApiCRM/pull/42
```

**Test cases:**
1. `test_upsert_pr_creates_file` — new PR creates file in `entities/prs/`
2. `test_upsert_pr_idempotent` — second call returns `(path, False)`
3. `test_upsert_pr_includes_author_wikilink` — body contains `[[Person Name]]`
4. `test_upsert_pr_includes_project_wikilink` — body contains `[[Project]]`
5. `test_upsert_pr_no_author` — handles missing author gracefully
6. `test_upsert_pr_no_project` — handles missing project_ref

**Acceptance criteria:**
- PR files written to `entities/prs/`
- Idempotent (skip if exists)
- Frontmatter + body consistent with existing entity patterns

**Dependencies:** Tasks 2, 4.

---

## Task 6: Card Entity Enrichment — Persons + Project

**Files to modify:**
- `vault/ingest/entity_writer.py` — update `upsert_card()` template
- `vault/tests/test_crosslink_builder.py`

**Changes to card template:**
Add sections after `## Dados`:
```markdown
## Pessoas
- [[Lincoln Quinan Junior]]
- [[Robert Urech]]

## Projeto
- [[BAT/Kaba]]
```

**Approach:** Update `upsert_card()` to accept optional `_persons` and `_project` fields on the entity dict and render them.

**Test cases:**
1. `test_upsert_card_with_persons` — card file includes `## Pessoas` with wiki-links
2. `test_upsert_card_with_project` — card file includes `## Projeto` section
3. `test_upsert_card_without_persons` — no `## Pessoas` section when empty
4. `test_upsert_card_idempotent_still_works` — existing cards not broken

**Acceptance criteria:**
- Card entities enriched with person wiki-links and project link
- Backward compatible (cards without persons/project still work)

**Dependencies:** Tasks 3, 5.

---

## Task 7: Crosslink Builder — Main Orchestration Module

**Files to modify:**
- `vault/ingest/crosslink_builder.py` — main `run_crosslink()` function
- `vault/tests/test_crosslink_builder.py`

**`run_crosslink()` function:**
```python
def run_crosslink(
    vault_root: Path,
    dry_run: bool = False,
    trello_api_key: str | None = None,
    trello_token: str | None = None,
    github_token: str | None = None,
) -> dict[str, Any]:
    """Stage 8: Cross-link cards and PRs to persons and projects.
    
    Steps:
    1. Load mapping configs
    2. For each card entity: resolve members → persons, resolve board → project
    3. For each PR (from enrichment_context + GitHub API): resolve author → person, resolve repo → project
    4. Write relationship files (card-person, card-project, pr-person, pr-project)
    5. Upsert PR entities
    6. Enrich card entities with persons/project
    7. Enrich project entities with cards/PRs/persons
    8. Enrich person entities with cards/PRs
    """
```

**Test cases:**
1. `test_run_crosslink_dry_run` — returns summary, no files written
2. `test_run_crosslink_creates_relationships` — all 4 relationship files written
3. `test_run_crosslink_resolves_card_to_person` — card-person edge created
4. `test_run_crosslink_resolves_pr_to_person` — pr-person edge created
5. `test_run_crosslink_resolves_card_to_project` — card-project edge created
6. `test_run_crosslink_resolves_pr_to_project` — pr-project edge created
7. `test_run_crosslink_no_cards` — handles empty vault gracefully
8. `test_run_crosslink_unmapped_entities` — skips unmapped without error

**Acceptance criteria:**
- Orchestration works end-to-end
- All relationship files produced
- Dry-run mode works

**Dependencies:** Tasks 3, 4, 5, 6.

---

## Task 8: Project Enrichment — Cards/PRs/Persons Sections

**Files to modify:**
- `vault/ingest/crosslink_builder.py` — add `_enrich_project_files()`
- `vault/tests/test_crosslink_builder.py`

**Updates to project entity template:**
```markdown
## Cards
- [[card-board1-card1|Card Title]]

## PRs
- [[pr-repo-42|PR Title]]

## Pessoas
- [[Lincoln Quinan Junior]]
- [[Robert Urech]]
```

**Test cases:**
1. `test_enrich_project_adds_cards` — project file gets `## Cards` section
2. `test_enrich_project_adds_prs` — project file gets `## PRs` section
3. `test_enrich_project_adds_persons` — project file gets `## Pessoas` section
4. `test_enrich_project_no_new_data` — existing sections preserved when no new data
5. `test_enrich_project_creates_new_project` — new project entity created if cards/PRs reference unmapped project

**Acceptance criteria:**
- Project hub pages enriched with cross-links
- New projects auto-created

**Dependencies:** Task 7.

---

## Task 9: Person Enrichment — Cards/PRs Sections

**Files to modify:**
- `vault/ingest/crosslink_builder.py` — add `_enrich_person_files_with_crosslinks()`
- `vault/tests/test_crosslink_builder.py`

**Updates to person entity template:**
```markdown
## Cards
- [[card-board1-card1|Card Title]]

## PRs
- [[pr-repo-42|PR Title]]
```

**Test cases:**
1. `test_enrich_person_adds_cards` — person file gets `## Cards` section with wiki-links
2. `test_enrich_person_adds_prs` — person file gets `## PRs` section with wiki-links
3. `test_enrich_person_preserves_meetings` — existing `## Reuniões` section untouched
4. `test_enrich_person_no_data` — person with no cards/PRs unchanged
5. `test_enrich_person_draft_person` — draft person created for unmapped member gets cards too

**Acceptance criteria:**
- Person pages enriched with card and PR wiki-links
- Existing sections preserved

**Dependencies:** Task 7.

---

## Task 10: Meeting Context Update — Project-Scoped Links

**Files to modify:**
- `vault/ingest/crosslink_builder.py` — add `_update_meeting_context()`
- `vault/tests/test_crosslink_builder.py`

**What changes:**
Currently meetings use date-proximity linking (enrichment_context in Supabase has Trello cards and GitHub PRs from same time window). Replace with project-scoped context:
- For each meeting, detect project (via `_detect_project()` already in `external_ingest.py`)
- Show cards/PRs linked to that same project (not same date window)
- This is a display concern — the meeting entity body gets updated `## Contexto` section

**Test cases:**
1. `test_update_meeting_context_with_project_cards` — meeting shows project-scoped cards
2. `test_update_meeting_context_with_project_prs` — meeting shows project-scoped PRs
3. `test_update_meeting_context_no_project` — meeting without project detection unchanged
4. `test_update_meeting_context_replaces_date_proximity` — old date-based links replaced

**Acceptance criteria:**
- Meeting context section shows project-scoped entities
- Date-proximity links removed

**Dependencies:** Tasks 7, 8.

---

## Task 11: Pipeline Integration — Stage 8 in `external_ingest.py`

**Files to modify:**
- `vault/ingest/external_ingest.py` — add crosslink stage after card persist and GitHub enrichment

**Changes:**
Add after the GitHub enrichment block (Stage 7) in `_run_ingest_inner()`:
```python
# Stage 8 — Cross-linking
crosslink_result = {}
try:
    from vault.ingest.crosslink_builder import run_crosslink
    if not dry_run:
        crosslink_result = run_crosslink(
            vault_root=vault_root,
            trello_api_key=os.environ.get("TRELLO_API_KEY"),
            trello_token=os.environ.get("TRELLO_TOKEN"),
            github_token=os.environ.get("GITHUB_PERSONAL_ACCESS_TOKEN"),
        )
except Exception as exc:
    errors.append({"source": "crosslink", "error": str(exc), "type": type(exc).__name__})
```

**Test cases:**
1. `test_pipeline_includes_crosslink_stage` — `_run_ingest_inner` calls `run_crosslink`
2. `test_pipeline_crosslink_error_handled` — crosslink failure doesn't break pipeline
3. `test_pipeline_crosslink_counts_in_result` — result includes crosslink stats

**Acceptance criteria:**
- Crosslink runs as Stage 8 in pipeline
- Errors don't break the pipeline
- Stats included in result dict

**Dependencies:** Task 7.

---

## Task 12: Index Update — Include New Entity Types

**Files to modify:**
- `vault/ingest/index_manager.py` — include PRs in `rebuild_index()`
- `vault/tests/test_crosslink_builder.py`

**Changes:**
- `rebuild_index()` should scan `entities/prs/` and include PR entities
- Add `🔀 PRs` section to index.md
- Update stats to include PR count

**Test cases:**
1. `test_index_includes_prs` — index.md has PR section
2. `test_index_pr_count_correct` — PR count matches files
3. `test_index_stats_include_prs` — stats line includes PR count

**Acceptance criteria:**
- Index includes PR entities
- Stats accurate

**Dependencies:** Task 5.

---

## Task 13: Lint Update — Cover New Entity Types and Relationships

**Files to modify:**
- `vault/ingest/vault_lint_scanner.py` — add PR entity scanning, new relationship file scanning
- `vault/tests/test_lint.py`

**Changes:**
- Scan `entities/prs/` for orphans/stale
- Count relationships in `card-person.json`, `pr-person.json`, `card-project.json`, `pr-project.json`
- Check for dangling wiki-links (card references person that doesn't exist)
- Check for unmapped members (card has member IDs not in mapping)

**Test cases:**
1. `test_lint_scans_pr_entities` — PRs included in entity count
2. `test_lint_counts_crosslink_relationships` — all 4 relationship files counted
3. `test_lint_detects_dangling_card_person` — card links to nonexistent person
4. `test_lint_detects_unmapped_trello_member` — card has unmapped member ID
5. `test_lint_pr_orphan_detection` — PR not in index flagged as orphan

**Acceptance criteria:**
- Lint covers all new entity types
- New relationship files scanned
- New edge cases detected

**Dependencies:** Tasks 5, 7.

---

## Task 14: Integration Test — Full Pipeline with Real Data Shape

**Files to modify:**
- `vault/tests/test_crosslink_builder.py` — add integration test class

**Test cases:**
1. `test_full_crosslink_pipeline` — end-to-end with mock data:
   - Create temp vault with sample meetings, persons, cards
   - Run `run_crosslink()`
   - Assert: PR entities created, card entities enriched, relationship files written, project/person pages updated, meeting context updated
2. `test_crosslink_idempotency` — run twice, same result
3. `test_crosslink_with_partial_data` — some cards without members, some PRs without author
4. `test_crosslink_performance` — 100 cards, 50 PRs completes in <5s

**Acceptance criteria:**
- Full pipeline test passes
- Idempotency verified
- Edge cases handled

**Dependencies:** Tasks 7–11.

---

## Task 15: Documentation — Update VAULT.md

**Files to modify:**
- `memory/vault/VAULT.md`

**Changes:**
- Update architecture diagram to include crosslink stage
- Document new entity types (PR)
- Document new relationship files
- Document mapping configs
- Update pipeline stages (add Stage 8)
- Update "Evolução" table (mark Cards/PRs as ✅ done)

**Acceptance criteria:**
- VAULT.md reflects all changes
- Diagram updated
- No stale references

**Dependencies:** Tasks 7–13.

---

## Task 16: PR — Create Pull Request

**Steps:**
1. Ensure all tests pass: `python3 -m pytest vault/tests/ -q --tb=short`
2. Run lint: verify no regressions
3. Squash or regular commits with conventional messages:
   - `feat(crosslink): add mapping config loader`
   - `feat(crosslink): add Trello member resolution`
   - `feat(crosslink): add GitHub PR author resolution`
   - `feat(entity): add upsert_pr() writer`
   - `feat(crosslink): add crosslink builder orchestration`
   - `feat(crosslink): add project/person enrichment`
   - `feat(crosslink): replace date-proximity with project-scoped meeting context`
   - `feat(pipeline): integrate crosslink as Stage 8`
   - `feat(index): include PR entities in index`
   - `feat(lint): cover crosslink entities and relationships`
   - `docs: update VAULT.md for crosslink pipeline`
4. Create PR to master with description of all changes

**PR description template:**
```markdown
## Cross-Linking Pipeline

### What
Links Trello Cards and GitHub PRs to Persons and Projects (not meetings by date proximity).
Meetings get context transitively via projects.

### New Entities
- PR entities (`entities/prs/`)

### New Relationships
- `card-person.json`
- `card-project.json`
- `pr-person.json`
- `pr-project.json`

### Mapping Configs
- `trello-member-map.yaml`
- `repo-project-map.yaml`
- `board-project-map.yaml`

### Pipeline Stage 8
Crosslink runs after GitHub enrichment, resolving members and authors to persons,
boards/repos to projects, and enriching all entity pages with wiki-links.

### Tests
All TDD — 40+ new test cases covering mapping, resolution, entity creation,
relationships, enrichment, edge cases, and integration.
```

**Acceptance criteria:**
- All tests green
- PR created
- No lint regressions

**Dependencies:** Tasks 1–15.

---

## Relationship File Schemas

### `card-person.json`
```json
{
  "edges": [
    {
      "from_id": "card:board123:card456",
      "to_id": "person:tldv:abc",
      "role": "assignee",
      "confidence": "high",
      "sources": [{"source_type": "trello_api", "source_ref": "trello:board123:card456"}]
    }
  ]
}
```

### `pr-person.json`
```json
{
  "edges": [
    {
      "from_id": "pr:living/repo:42",
      "to_id": "person:github:lincolnq",
      "role": "author",
      "confidence": "high",
      "sources": [{"source_type": "github_api", "source_ref": "github:living/repo:42"}]
    }
  ]
}
```

### `card-project.json`
```json
{
  "edges": [
    {
      "from_id": "card:board123:card456",
      "to_id": "project:BAT/Kaba",
      "role": "belongs_to",
      "confidence": "high",
      "sources": [{"source_type": "board_project_map", "source_ref": "board:board123"}]
    }
  ]
}
```

### `pr-project.json`
```json
{
  "edges": [
    {
      "from_id": "pr:living/repo:42",
      "to_id": "project:BAT/Kaba",
      "role": "belongs_to",
      "confidence": "high",
      "sources": [{"source_type": "repo_project_map", "source_ref": "repo:living/repo"}]
    }
  ]
}
```
