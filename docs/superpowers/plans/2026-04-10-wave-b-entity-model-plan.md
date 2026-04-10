# Wave B — Entity Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materializar entidades canônicas `person`, `project`, `repo` no vault com resolution de identidade semi-automática e observabilidade completa.

**Architecture:** Três módulos de ingest (TLDV participants, GitHub repos/contributors) convergem para writers canônicos por tipo de entidade. Identity resolver mantém resolution table append-only e decide merges via score threshold. Entity lint + quality report extendem a infraestrutura Wave A.

**Tech Stack:** Python 3.12, pytest, YAML frontmatter, JSONL append-only, GitHub REST API, TLDV pipeline existente.

---

## File Structure

```
vault/
├── domain/
│   ├── person_entity.py      # Person frontmatter schema + validation
│   ├── project_entity.py      # Project frontmatter schema + validation
│   └── repo_entity.py        # Repo frontmatter schema + validation
├── ingest/
│   ├── person_ingest.py      # TLDV participants → person canonical
│   ├── project_ingest.py     # TLDV topic_ref + GitHub topics → project
│   └── repo_ingest.py       # GitHub repos API → repo + contributors
├── identity/
│   └── resolver.py           # Resolution table + merge matrix
├── quality/
│   ├── entity_lint.py        # Entity-specific lint rules (extend domain_lint)
│   └── entity_quality.py     # Entity stats additions to quality report
├── tests/
│   ├── test_person_entity.py
│   ├── test_project_entity.py
│   ├── test_repo_entity.py
│   ├── test_resolver.py
│   └── test_entity_ingest.py
memory/vault/
├── entities/
│   ├── person/               # person:<slug>.md
│   ├── project/              # project:<slug>.md
│   └── repo/                # repo:<slug>.md
├── .resolution-cache.jsonl   # Append-only identity resolution log
└── .merge-candidates.jsonl  # Pending merge reviews
```

---

## Task 1: Domain Types — Person, Project, Repo

**Files:**
- Create: `vault/domain/person_entity.py`
- Create: `vault/domain/project_entity.py`
- Create: `vault/domain/repo_entity.py`
- Create: `vault/tests/test_person_entity.py`
- Create: `vault/tests/test_project_entity.py`
- Create: `vault/tests/test_repo_entity.py`

### Person Entity

- [ ] **Step 1: Write failing test**

```python
# vault/tests/test_person_entity.py
from vault.domain.person_entity import PersonEntity, PERSON_REQUIRED_FIELDS

def test_person_frontmatter_fields():
    e = PersonEntity(
        slug="robert",
        name="Robert Silva",
        sources=[{"source_type": "tldv_api", "source_ref": "tldv:participant:123", "retrieved_at": "2026-04-10T00:00:00Z", "mapper_version": "wave-b-person-v1"}],
    )
    fm = e.to_frontmatter()
    assert fm["id_canonical"].startswith("person:")
    assert fm["slug"] == "robert"
    assert fm["type"] == "person"
    assert fm["name"] == "Robert Silva"
    assert fm["first_seen_at"] == fm["last_seen_at"]
    assert fm["confidence"] in ("low", "medium", "high")
    assert fm["stale"] == False
    assert fm["draft"] == False
```

- [ ] **Step 2: Run test — verify RED**

Run: `python3 -m pytest vault/tests/test_person_entity.py -v --tb=short`
Expected: FAIL — module not found

- [ ] **Step 3: Implement person_entity.py**

```python
# vault/domain/person_entity.py
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import yaml

PERSON_REQUIRED_FIELDS = ["id_canonical", "slug", "type", "name", "sources",
                          "first_seen_at", "last_seen_at", "confidence",
                          "stale", "draft"]

PERSON_MAPPER_VERSION = "wave-b-person-v1"

class PersonEntity:
    def __init__(
        self,
        slug: str,
        name: str,
        sources: list[dict],
        source_id: str = "",
        aliases: list[str] | None = None,
        confidence: str = "medium",
        signals: list[dict] | None = None,
    ):
        self.slug = slug
        self.name = name
        self.sources = sources
        self.source_id = source_id or slug
        self.aliases = aliases or []
        self.confidence = confidence
        self.signals = signals or []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.first_seen_at = now
        self.last_seen_at = now

    @property
    def id_canonical(self) -> str:
        return f"person:tldv:{self.source_id}"

    def to_frontmatter(self) -> dict:
        return {
            "id_canonical": self.id_canonical,
            "slug": self.slug,
            "type": "person",
            "name": self.name,
            "sources": self.sources,
            "aliases": self.aliases,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "confidence": self.confidence,
            "signals": self.signals,
            "verification_log": [],
            "stale": False,
            "draft": False,
        }

    def to_yaml(self) -> str:
        from io import StringIO
        buf = StringIO()
        yaml.dump(self.to_frontmatter(), buf, default_flow_style=False, allow_unicode=True, sort_keys=False)
        return buf.getvalue()

    def write(self, vault_root: Path):
        path = vault_root / "entities" / "person" / f"{self.slug}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        fm = self.to_frontmatter()
        content = f"---\n{yaml.dump(fm, default_flow_style=False, allow_unicode=True, sort_keys=False)}---\n"
        path.write_text(content, encoding="utf-8")
        return path
```

- [ ] **Step 4: Run test — verify GREEN**

Run: `python3 -m pytest vault/tests/test_person_entity.py -v --tb=short`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vault/domain/person_entity.py vault/tests/test_person_entity.py
git commit -m "feat(vault/domain): add PersonEntity canonical type and tests"
```

### Project Entity

- [ ] **Step 1: Write failing test** (similar pattern to PersonEntity)
- [ ] **Step 2: Run test — verify RED**
- [ ] **Step 3: Implement project_entity.py** (id_canonical: `project:<fonte>:<id-estável>`)
- [ ] **Step 4: Run test — verify GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/domain/project_entity.py vault/tests/test_project_entity.py
git commit -m "feat(vault/domain): add ProjectEntity canonical type and tests"
```

### Repo Entity

- [ ] **Step 1: Write failing test**
- [ ] **Step 2: Run test — verify RED**
- [ ] **Step 3: Implement repo_entity.py** (id_canonical: `repo:<owner>/<name>`)
- [ ] **Step 4: Run test — verify GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/domain/repo_entity.py vault/tests/test_repo_entity.py
git commit -m "feat(vault/domain): add RepoEntity canonical type and tests"
```

---

## Task 2: Identity Resolver

**Files:**
- Create: `vault/identity/resolver.py`
- Create: `vault/tests/test_resolver.py`
- Create: `memory/vault/.resolution-cache.jsonl` (empty, touch)
- Create: `memory/vault/.merge-candidates.jsonl` (empty, touch)

### Resolver

- [ ] **Step 1: Write failing tests**

```python
# vault/tests/test_resolver.py
from vault.identity.resolver import IdentityResolver, ResolutionCache

def test_resolver_registers_new_person(tmp_path):
    cache_file = tmp_path / "resolution.jsonl"
    resolver = IdentityResolver(cache_file)
    canonical = resolver.resolve_person(
        source="tldv",
        source_id="abc123",
        name="Robert Silva",
        email="robert@livingnet.com.br",
    )
    assert canonical.startswith("person:")
    assert resolver.get_canonical("tldv", "abc123") == canonical

def test_resolver_merge_auto_high_score():
    resolver = IdentityResolver(cache_file)
    score = resolver._compute_similarity("Robert Silva", "Robert S.")
    assert score >= 0.85  # high enough for auto-merge

def test_resolver_candidate_medium_score():
    resolver = IdentityResolver(cache_file)
    score = resolver._compute_similarity("Robert Silva", "Roberto Silva")
    assert 0.60 <= score < 0.85  # ambiguous — candidate

def test_resolution_cache_append_only(tmp_path):
    cache_file = tmp_path / "resolution.jsonl"
    resolver = IdentityResolver(cache_file)
    resolver.resolve_person(source="tldv", source_id="abc", name="Test")
    resolver.resolve_person(source="github", source_id="xyz", name="Test")
    lines = cache_file.read_text().strip().split("\n")
    assert len(lines) == 2  # append-only
```

- [ ] **Step 2: Run test — verify RED**
- [ ] **Step 3: Implement resolver.py**

Key implementation:

```python
# vault/identity/resolver.py
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path

MERGE_SCORE_AUTO = 0.85
MERGE_SCORE_CANDIDATE = 0.60

def _normalize_name(name: str) -> str:
    import unicodedata
    n = unicodedata.normalize("NFKD", name)
    import re
    n = re.sub(r"[^a-z0-9\s]", "", n.lower())
    return " ".join(n.split())

def _levenshtein(a, b):
    # simple Levenshtein distance
    if len(a) < len(b):
        return _levenshtein(b, a)
    if len(b) == 0:
        return len(a)
    prev = range(len(b) + 1)
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]

class IdentityResolver:
    def __init__(self, cache_path: Path):
        self.cache_path = cache_path
        if not cache_path.exists():
            cache_path.write_text("", encoding="utf-8")

    def _load_cache(self) -> list[dict]:
        lines = self.cache_path.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(l) for l in lines if l]

    def _append(self, entry: dict):
        with self.cache_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def get_canonical(self, source: str, source_id: str) -> str | None:
        for entry in self._load_cache():
            if entry["source"] == source and entry["source_id"] == source_id:
                return entry["canonical_id"]
        return None

    def _compute_similarity(self, name1: str, name2: str) -> float:
        n1 = _normalize_name(name1)
        n2 = _normalize_name(name2)
        if n1 == n2:
            return 1.0
        max_len = max(len(n1), len(n2))
        if max_len == 0:
            return 1.0
        dist = _levenshtein(n1, n2)
        return 1.0 - (dist / max_len)

    def resolve_person(self, source: str, source_id: str, name: str, email: str = "") -> str:
        # Already resolved?
        existing = self.get_canonical(source, source_id)
        if existing:
            return existing

        # Find potential matches
        candidates = self._load_cache()
        for entry in candidates:
            if entry["canonical_id"].startswith("person:"):
                sim = self._compute_similarity(name, entry.get("name", ""))
                if sim >= MERGE_SCORE_AUTO:
                    canonical = entry["canonical_id"]
                    self._append({
                        "canonical_id": canonical,
                        "source": source,
                        "source_id": source_id,
                        "name": name,
                        "resolved_at": datetime.now(timezone.utc).isoformat(),
                        "auto_merged": True,
                    })
                    return canonical
                elif sim >= MERGE_SCORE_CANDIDATE:
                    # record candidate
                    pass

        # New person
        import uuid
        canonical = f"person:{source}:{source_id}"
        self._append({
            "canonical_id": canonical,
            "source": source,
            "source_id": source_id,
            "name": name,
            "resolved_at": datetime.now(timezone.utc).isoformat(),
            "auto_merged": False,
        })
        return canonical
```

- [ ] **Step 4: Run tests — verify GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/identity/resolver.py vault/tests/test_resolver.py memory/vault/.resolution-cache.jsonl memory/vault/.merge-candidates.jsonl
git commit -m "feat(vault/identity): add identity resolver with append-only cache and merge score"
```

---

## Task 3: Ingest — Person from TLDV

**Files:**
- Create: `vault/ingest/person_ingest.py`
- Extend: `vault/ingest/__init__.py` (if exists)

- [ ] **Step 1: Write failing tests**

```python
# vault/tests/test_entity_ingest.py
from vault.ingest.person_ingest import TLDVPersonIngest, _normalize_participant_name

def test_normalize_name():
    assert _normalize_participant_name("Robert Silva") == "robert-silva"
    assert _normalize_participant_name("João Paulo") == "joao-paulo"

def test_person_ingest_from_tldv_meeting(tmp_path, monkeypatch):
    monkeypatch.setenv("TLDV_API_TOKEN", "fake-token")
    from vault.ingest.person_ingest import TLDVPersonIngest
    ingest = TLDVPersonIngest(cache_path=tmp_path / "resolution.jsonl")
    meeting = {
        "participants": [
            {"id": "p1", "name": "Robert Silva", "email": "robert@livingnet.com.br"},
            {"id": "p2", "name": "Pedro Santos", "email": "pedro@livingnet.com.br"},
        ]
    }
    persons = ingest.from_meeting(meeting)
    assert len(persons) == 2
    assert all(p.slug for p in persons)
    assert all(p.name for p in persons)
    assert all(p.id_canonical.startswith("person:") for p in persons)
```

- [ ] **Step 2: Run test — verify RED**
- [ ] **Step 3: Implement person_ingest.py**

```python
# vault/ingest/person_ingest.py
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import json
import requests
from vault.domain.person_entity import PersonEntity, PERSON_MAPPER_VERSION
from vault.identity.resolver import IdentityResolver

def _normalize_participant_name(name: str) -> str:
    import re, unicodedata
    n = unicodedata.normalize("NFKD", name)
    n = re.sub(r"[^a-z0-9\s]", "", n.lower())
    return "-".join(n.split())

class TLDVPersonIngest:
    def __init__(self, cache_path: Path, api_token: str | None = None):
        self.resolver = IdentityResolver(cache_path)
        self.api_token = api_token or __import__("os").getenv("TLDV_API_TOKEN", "")

    def from_meeting(self, meeting: dict) -> list[PersonEntity]:
        persons = []
        for p in meeting.get("participants", []):
            pid = p.get("id", "")
            name = p.get("name", "").strip()
            email = p.get("email", "")
            if not name:
                continue
            slug = _normalize_participant_name(name)
            canonical = self.resolver.resolve_person(
                source="tldv", source_id=pid, name=name, email=email
            )
            source_record = {
                "source_type": "tldv_api",
                "source_ref": f"tldv:participant:{pid}",
                "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "mapper_version": PERSON_MAPPER_VERSION,
            }
            entity = PersonEntity(
                slug=slug,
                name=name,
                sources=[source_record],
                source_id=pid,
                aliases=[email] if email else [],
            )
            persons.append(entity)
        return persons

    def from_recent_meetings(self, days: int = 7) -> list[PersonEntity]:
        # Integration with existing TLDV pipeline
        # Reuses fetch logic from vault/enrich_github.py or vault/pipeline.py
        from vault.pipeline import fetch_tldv_meetings
        meetings = fetch_tldv_meetings(days=days)
        all_persons = []
        for meeting in meetings:
            all_persons.extend(self.from_meeting(meeting))
        return all_persons
```

- [ ] **Step 4: Run test — verify GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/ingest/person_ingest.py vault/tests/test_entity_ingest.py
git commit -m "feat(vault/ingest): add TLDV participant ingest for person entities"
```

---

## Task 4: Ingest — Repo + Project from GitHub

**Files:**
- Create: `vault/ingest/repo_ingest.py`
- Create: `vault/ingest/project_ingest.py`
- Extend: `vault/tests/test_entity_ingest.py`

- [ ] **Step 1: Write failing tests**

```python
# vault/tests/test_entity_ingest.py
from vault.ingest.repo_ingest import GitHubRepoIngest
from vault.ingest.project_ingest import GitHubProjectIngest

def test_repo_ingest_from_api_response(tmp_path):
    ingest = GitHubRepoIngest(cache_path=tmp_path / "resolution.jsonl")
    repo_data = {
        "full_name": "living/livy-memory-bot",
        "name": "livy-memory-bot",
        "owner": {"login": "living"},
        "default_branch": "master",
        "language": "Python",
    }
    entity = ingest.from_repo_data(repo_data)
    assert entity.id_canonical == "repo:living/livy-memory-bot"
    assert entity.slug == "livy-memory-bot"
    assert entity.owner == "living"

def test_project_ingest_from_topics(tmp_path):
    ingest = GitHubProjectIngest(cache_path=tmp_path / "resolution.jsonl")
    topics = ["bat", "conectabot", "observability"]
    entities = ingest.from_topics(topics, repo_ref="living/livy-bat-jobs")
    assert len(entities) >= 1
    assert all(e.id_canonical.startswith("project:") for e in entities)
```

- [ ] **Step 2: Run tests — verify RED**
- [ ] **Step 3: Implement repo_ingest.py + project_ingest.py**

repo_ingest.py:
```python
# vault/ingest/repo_ingest.py
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import os
import requests
from vault.domain.repo_entity import RepoEntity, REPO_MAPPER_VERSION
from vault.identity.resolver import IdentityResolver

GITHUB_TOKEN = os.getenv("GITHUB_PERSONAL_ACCESS_TOKEN", "")
HEADERS = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}

class GitHubRepoIngest:
    def __init__(self, cache_path: Path):
        self.resolver = IdentityResolver(cache_path)

    def from_repo_data(self, repo_data: dict) -> RepoEntity:
        full_name = repo_data["full_name"]
        owner = repo_data.get("owner", {}).get("login", "")
        name = repo_data.get("name", full_name.split("/")[-1])
        entity = RepoEntity(
            full_name=full_name,
            name=name,
            owner=owner,
            default_branch=repo_data.get("default_branch", "main"),
            language=repo_data.get("language", ""),
        )
        return entity

    def from_org(self, org: str = "living") -> list[RepoEntity]:
        resp = requests.get(
            f"https://api.github.com/orgs/{org}/repos",
            headers=HEADERS,
            params={"per_page": 100},
            timeout=30,
        )
        resp.raise_for_status()
        repos = resp.json()
        return [self.from_repo_data(r) for r in repos]
```

project_ingest.py:
```python
# vault/ingest/project_ingest.py
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
from vault.domain.project_entity import ProjectEntity, PROJECT_MAPPER_VERSION
from vault.identity.resolver import IdentityResolver

def _normalize_topic(topic: str) -> str:
    import re, unicodedata
    n = unicodedata.normalize("NFKD", topic)
    n = re.sub(r"[^a-z0-9\s]", "", n.lower())
    return "-".join(n.split())

class GitHubProjectIngest:
    def __init__(self, cache_path: Path):
        self.resolver = IdentityResolver(cache_path)

    def from_topics(self, topics: list[str], repo_ref: str = "") -> list[ProjectEntity]:
        entities = []
        for topic in topics:
            slug = _normalize_topic(topic)
            if len(slug) < 2:
                continue
            entity = ProjectEntity(
                slug=slug,
                name=topic,
                sources=[{
                    "source_type": "github_api",
                    "source_ref": f"github:topic:{topic}",
                    "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "mapper_version": PROJECT_MAPPER_VERSION,
                }],
                repo_ref=repo_ref,
            )
            entities.append(entity)
        return entities
```

- [ ] **Step 4: Run tests — verify GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/ingest/repo_ingest.py vault/ingest/project_ingest.py vault/tests/test_entity_ingest.py
git commit -m "feat(vault/ingest): add GitHub repo and project ingest"
```

---

## Task 5: Entity Quality — Lint + Report

**Files:**
- Create: `vault/quality/entity_lint.py`
- Create: `vault/quality/entity_quality.py`
- Create: `vault/tests/test_entity_lint.py`
- Create: `vault/tests/test_entity_quality.py`
- Modify: `vault/quality/domain_lint.py` (add entity type detection)
- Modify: `vault/quality/quality_review.py` (add entity_stats section)

### Entity Lint

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run test — verify RED**
- [ ] **Step 3: Implement entity_lint.py**

```python
# vault/quality/entity_lint.py
from __future__ import annotations
from pathlib import Path
import yaml

def run_entity_lint(vault_root: Path) -> dict:
    issues = []
    for sub in ("person", "project", "repo"):
        entity_dir = vault_root / "entities" / sub
        if not entity_dir.exists():
            continue
        for md in entity_dir.glob("*.md"):
            fm = _parse_fm(md)
            if not fm.get("name") and sub != "repo":
                issues.append(f"{md.name}: missing name")
            if not fm.get("id_canonical"):
                issues.append(f"{md.name}: missing id_canonical")
            if fm.get("confidence") == "high" and len(fm.get("sources", [])) < 2:
                issues.append(f"{md.name}: high confidence but single source")
    return {"valid": len(issues) == 0, "issues": issues, "total_errors": len(issues)}

def _parse_fm(path: Path) -> dict:
    text = path.read_text(encoding="utf-8").lstrip()
    if not text.startswith("---"):
        return {}
    try:
        end = text.index("\n---", 3)
        return yaml.safe_load(text[3:end]) or {}
    except Exception:
        return {}
```

- [ ] **Step 4: Run test — verify GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/quality/entity_lint.py vault/tests/test_entity_lint.py
git commit -m "feat(vault/quality): add entity-specific lint rules"
```

### Entity Quality Report

- [ ] **Step 1: Write failing tests**
- [ ] **Step 2: Run test — verify RED**
- [ ] **Step 3: Implement entity_quality.py** (adds entity_stats to existing quality report)
- [ ] **Step 4: Run test — verify GREEN**
- [ ] **Step 5: Commit**

```bash
git add vault/quality/entity_quality.py vault/tests/test_entity_quality.py
git commit -m "feat(vault/quality): add entity stats to quality report"
```

---

## Task 6: Index + Backlinks + Docs

**Files:**
- Modify: `memory/vault/index.md` (add person/project/repo sections)
- Create: `vault/backlinks.py` (retroactive backlink scanner)
- Modify: `CLAUDE.md` (add entity ingest commands)

- [ ] **Step 1: Write failing tests for backlinks**
- [ ] **Step 2: Run test — verify RED**
- [ ] **Step 3: Implement backlinks.py** — scan decisions for `[[entities/person/...]]` and update `linked_from`
- [ ] **Step 4: Run test — verify GREEN**
- [ ] **Step 5: Update index.md** with person/project/repo sections
- [ ] **Step 6: Update CLAUDE.md** with Wave B runbook

Run: `grep -n "Wave" CLAUDE.md` to verify section

- [ ] **Step 7: Commit**

```bash
git add memory/vault/index.md vault/backlinks.py CLAUDE.md
git commit -m "chore(vault): add person/project/repo sections to index and Wave B runbook"
```

---

## Task 7: Full Integration + Regression

- [ ] **Step 1: Run full test suite**

Run: `python3 -m pytest vault/tests/ -q --tb=no`
Expected: 0 failures (all new tests pass)

- [ ] **Step 2: Run domain lint**

Run:
```python
python3 -c "
from pathlib import Path
from vault.quality.entity_lint import run_entity_lint
r = run_entity_lint(Path('memory/vault'))
print(r)
assert r['valid'] == True
"
```

- [ ] **Step 3: Run entity quality**

Run:
```python
python3 -c "
from pathlib import Path
from vault.quality.entity_quality import generate_entity_stats
s = generate_entity_stats(Path('memory/vault'))
print(s)
"
```

- [ ] **Step 4: Commit verification artifacts**

```bash
git add memory/vault/quality-review memory/vault/lint-reports
git commit -m "chore(vault): add Wave B verification artifacts"
```

- [ ] **Step 5: Push + PR**

```bash
git push origin feature/wave-b-entity-model
gh pr create --repo living/livy-memory-bot --title "feat(vault): Wave B entity model (person/project/repo)" --body "Wave B: person, project, repo entity types with identity resolution." --base master --draft
```

---

## Test Matrix

| Layer | Command | Pass Criteria |
|---|---|---|
| Domain types | `pytest vault/tests/test_person_entity.py vault/tests/test_project_entity.py vault/tests/test_repo_entity.py -v` | 100% green |
| Resolver | `pytest vault/tests/test_resolver.py -v` | 100% green |
| Ingest | `pytest vault/tests/test_entity_ingest.py -v` | 100% green |
| Entity lint | `python3 -c "from vault.quality.entity_lint import...; assert run_entity_lint(Path('memory/vault'))['valid']"` | valid=True |
| Quality report | `pytest vault/tests/test_entity_quality.py -v` | 100% green |
| Regression | `pytest vault/tests/ -q --tb=no` | 0 failures |

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| TLDV API rate limit | Batch with 1h cache; only fetch meetings from last 7 days |
| GitHub API rate limit | org=living only (few repos); exponential backoff |
| Identity false merge | Score threshold 0.85 for auto; candidates logged separately |
| Missing TLDV token | Graceful degradation; log warning, skip ingest |
