# Vault Quality Fixes — Person Dedup, Meeting Enrichment, Project Filter

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the 4 structural problems in the Living Memory vault: duplicate persons, empty meeting summaries, irrelevant project context, and no continuous enrichment.

**Architecture:** The vault pipeline is 100% mechanical (fetch → stub → write). We add: (1) an identity map YAML + merge service that runs during ingest, (2) an LLM enrichment stage that fills meeting summaries, (3) a relevance filter for enrichment_context, and (4) a lint-and-fix loop. Each task is independent and testable.

**Tech Stack:** Python 3.11, PyYAML, Pydantic (optional), Supabase, Trello API, OpenAI-compatible LLM (via OmniRoute).

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `vault/domain/identity_map.py` | Create | Load/resolve known person aliases from YAML config |
| `vault/domain/identity_map.yaml` | Create | Human-curated identity mappings |
| `vault/domain/identity_merger.py` | Create | Merge duplicate person files on disk |
| `vault/ingest/person_ingest.py` | Modify | Add identity_map lookup during person creation |
| `vault/ingest/entity_writer.py` | Modify | Use identity_map in `upsert_person` + `_find_existing_person_fuzzy` |
| `vault/ingest/crosslink_builder.py` | Modify | Use identity_map when resolving card members and PR authors |
| `vault/enrich/llm_summarize.py` | Create | LLM-based meeting summary extraction |
| `vault/enrich/relevance_filter.py` | Create | Filter enrichment_context cards/PRs to relevant subset |
| `vault/ingest/external_ingest.py` | Modify | Add LLM enrichment + relevance filter stages |
| `vault/lint/auto_fix.py` | Create | Auto-fix orphans, stale, and gaps detected by lint |
| `vault/crons/vault_ingest_cron.py` | Modify | Add enrichment and merge stages |
| `vault/tests/test_identity_map.py` | Create | Tests for identity map loading and resolution |
| `vault/tests/test_identity_merger.py` | Create | Tests for person file merging |
| `vault/tests/test_llm_summarize.py` | Create | Tests for summary extraction |
| `vault/tests/test_relevance_filter.py` | Create | Tests for enrichment context filtering |

---

## Task 1: Identity Map — YAML Config + Loader

**Files:**
- Create: `vault/domain/identity_map.yaml`
- Create: `vault/domain/identity_map.py`
- Test: `vault/tests/test_identity_map.py`

The identity map is a curated YAML file mapping canonical person names to their known aliases across sources. This is the "ground truth" that the pipeline consults when creating or resolving persons.

- [ ] **Step 1: Write the identity map YAML**

```yaml
# vault/domain/identity_map.yaml
# Canonical identity map for Living Memory vault.
# Each entry has a canonical name and known aliases from different sources.

persons:
  - canonical: "Lincoln Quinan Junior"
    github_login: lincolnqjunior
    trello_names: [Lincoln]
    email: lincoln@livingnet.com.br
    aliases: [lincolnqjunior, Lincoln, Lincoln Quinan]

  - canonical: "Esteves Marques"
    github_login: estevesm
    trello_names: [esteves]
    aliases: [esteves, estevesm, Esteves]

  - canonical: "Victor Neves"
    github_login: victor-living
    trello_names: [victor neves, victorliving]
    aliases: [victor neves, victor-living, victorliving, Victor Hugo]

  - canonical: "Marcio Rocha"
    github_login: marcioxrocha
    trello_names: [marcio rocha]
    aliases: [marcio rocha, marcioxrocha, Marcio]

  - canonical: "Rafael Bernardi"
    trello_names: [Rafael Bernardi]
    aliases: [Rafael Bernardi]

  - canonical: "Caroliny Impellizieri"
    trello_names: [Caroliny Impellizieri]
    aliases: [Caroliny Impellizieri]

  - canonical: "Sergio Fraga"
    trello_names: [Sergio Fraga]
    aliases: [Sergio Fraga]

  - canonical: "Luiz Rogério"
    trello_names: [LuizR, "Luiz Rogério"]
    aliases: [LuizR, "Luiz Rogério", Luiz Rogerio]

  - canonical: "Jaime"
    trello_names: [jaime_living]
    aliases: [jaime_living, Jaime]
```

- [ ] **Step 2: Write the failing test**

```python
# vault/tests/test_identity_map.py
import pytest
from pathlib import Path


def test_load_identity_map():
    """Identity map loads from YAML and resolves known aliases."""
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    assert im is not None
    assert im.resolve_by_github("lincolnqjunior") == "Lincoln Quinan Junior"


def test_resolve_by_trello_name():
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    assert im.resolve_by_trello_name("esteves") == "Esteves Marques"
    assert im.resolve_by_trello_name("victorliving") == "Victor Neves"


def test_resolve_by_alias_fuzzy():
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    # Exact alias match
    assert im.resolve("Lincoln") == "Lincoln Quinan Junior"
    # Fuzzy: accent-insensitive
    assert im.resolve("luiz rogerio") == "Luiz Rogério"


def test_resolve_unknown_returns_none():
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    assert im.resolve("unknown_person_xyz") is None


def test_all_canonical_names_resolve():
    """Every canonical name should resolve to itself."""
    from vault.domain.identity_map import IdentityMap
    im = IdentityMap.load()
    for name in im.all_canonical_names():
        assert im.resolve(name) == name
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_identity_map.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'vault.domain.identity_map'`

- [ ] **Step 4: Write the identity_map.py implementation**

```python
# vault/domain/identity_map.py
"""Identity map — resolves person names from different sources to canonical identity.

Loads a curated YAML config (identity_map.yaml) that maps known aliases,
Trello names, and GitHub logins to a single canonical person name.
"""
from __future__ import annotations

import logging
import unicodedata
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger(__name__)

_DEFAULT_PATH = Path(__file__).parent / "identity_map.yaml"


def _strip_accents(s: str) -> str:
    """Remove diacritics for accent-insensitive matching."""
    return unicodedata.normalize("NFD", s).encode("ascii", "ignore").decode("ascii")


def _norm(s: str) -> str:
    """Normalize for matching: lowercase, accent-stripped, stripped."""
    return _strip_accents(s).strip().lower()


class IdentityMap:
    """Resolve person identifiers to canonical names."""

    def __init__(self, entries: list[dict]):
        self._entries = entries
        # Build lookup indices
        self._by_github: dict[str, str] = {}
        self._by_trello: dict[str, str] = {}
        self._by_alias: dict[str, str] = {}
        self._by_email: dict[str, str] = {}

        for entry in entries:
            canonical = entry["canonical"]
            # GitHub login
            gh = entry.get("github_login")
            if gh:
                self._by_github[gh.lower()] = canonical
                self._by_alias[_norm(gh)] = canonical
            # Trello names
            for tn in entry.get("trello_names", []):
                self._by_trello[_norm(tn)] = canonical
                self._by_alias[_norm(tn)] = canonical
            # Email
            email = entry.get("email")
            if email:
                self._by_email[email.lower().strip()] = canonical
            # Generic aliases
            for alias in entry.get("aliases", []):
                self._by_alias[_norm(alias)] = canonical
            # Canonical name itself
            self._by_alias[_norm(canonical)] = canonical

    @classmethod
    def load(cls, path: Path | None = None) -> "IdentityMap":
        """Load identity map from YAML file."""
        yaml_path = path or _DEFAULT_PATH
        if not yaml_path.exists():
            logger.warning("Identity map not found: %s", yaml_path)
            return cls(entries=[])
        with open(yaml_path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        entries = data.get("persons", [])
        return cls(entries=entries)

    def resolve_by_github(self, login: str) -> Optional[str]:
        """Resolve GitHub login to canonical name."""
        if not login:
            return None
        return self._by_github.get(login.lower())

    def resolve_by_trello_name(self, name: str) -> Optional[str]:
        """Resolve Trello display name to canonical name."""
        if not name:
            return None
        return self._by_trello.get(_norm(name))

    def resolve_by_email(self, email: str) -> Optional[str]:
        """Resolve email to canonical name."""
        if not email:
            return None
        return self._by_email.get(email.lower().strip())

    def resolve(self, name_or_login: str) -> Optional[str]:
        """Resolve any identifier to canonical name. Tries all indices."""
        if not name_or_login:
            return None
        norm = _norm(name_or_login)
        # Try exact matches first
        for lookup in (self._by_github, self._by_trello, self._by_alias, self._by_email):
            result = lookup.get(norm) or lookup.get(name_or_login.lower())
            if result:
                return result
        return None

    def all_canonical_names(self) -> list[str]:
        """Return all canonical person names."""
        return [e["canonical"] for e in self._entries]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_identity_map.py -v`
Expected: all 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add vault/domain/identity_map.py vault/domain/identity_map.yaml vault/tests/test_identity_map.py
git commit -m "feat(vault): add identity map YAML config and resolver"
```

---

## Task 2: Identity Merger — Extend `crosslink_dedup.py`

**Files:**
- Modify: `vault/ingest/crosslink_dedup.py` — use IdentityMap as ground truth
- Test: `vault/tests/test_identity_merger.py`

The existing `crosslink_dedup.py` already has `dedup_draft_persons()` with fuzzy matching, YAML merge, atomic writes, and quarantine. We extend it to use the IdentityMap as authoritative ground truth for matching, instead of relying solely on fuzzy heuristics.

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_identity_merger.py
import pytest
from pathlib import Path


def test_merge_two_person_files(tmp_path):
    """Merge a Trello person into a GitHub person, keeping canonical name."""
    from vault.domain.identity_merger import merge_person_files

    # Create two person files
    persons = tmp_path / "persons"
    persons.mkdir()

    # "Lincoln" (from Trello)
    lincoln_file = persons / "Lincoln.md"
    lincoln_file.write_text(
        "---\n"
        'entity: "Lincoln"\n'
        "type: person\n"
        "source_keys:\n"
        "  - trello-member:Lincoln\n"
        "---\n\n"
        "# Lincoln\n\n"
        "## Cards\n\n"
        "- [[card-1]]\n"
    )

    # "lincolnqjunior" (from GitHub)
    github_file = persons / "lincolnqjunior.md"
    github_file.write_text(
        "---\n"
        'entity: "lincolnqjunior"\n'
        "type: person\n"
        "github_login: lincolnqjunior\n"
        "source_keys:\n"
        "  - github:lincolnqjunior\n"
        "draft: true\n"
        "---\n\n"
        "# lincolnqjunior\n\n"
        "## PRs\n\n"
        "- [[pr-1]]\n"
    )

    # Merge: keep lincolnqjunior (canonical), absorb Lincoln
    result = merge_person_files(
        vault_root=tmp_path,
        keep_path=github_file,
        absorb_path=lincoln_file,
        canonical_name="Lincoln Quinan Junior",
    )

    assert result.merged is True
    # Keep file should have merged content
    text = github_file.read_text()
    assert "trello-member:Lincoln" in text
    assert "github:lincolnqjunior" in text
    assert "Lincoln Quinan Junior" in text
    assert "## Cards" in text
    assert "## PRs" in text
    # Absorb file should be moved to quarantine
    quarantine = persons / ".quarantine"
    assert (quarantine / "Lincoln.md").exists()
    assert not lincoln_file.exists()


def test_merge_skips_if_same_file(tmp_path):
    """Merge is a no-op if keep and absorb are the same file."""
    from vault.domain.identity_merger import merge_person_files

    persons = tmp_path / "persons"
    persons.mkdir()
    f = persons / "Test.md"
    f.write_text("---\nentity: Test\ntype: person\n---\n\n# Test\n")

    result = merge_person_files(
        vault_root=tmp_path,
        keep_path=f,
        absorb_path=f,
        canonical_name="Test",
    )
    assert result.merged is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_identity_merger.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Extend `crosslink_dedup.py` to use IdentityMap**

Add a new function `dedup_with_identity_map()` that uses the IdentityMap as authoritative ground truth, falling back to existing fuzzy logic for unmapped persons.

In `vault/ingest/crosslink_dedup.py`, add:

```python
def dedup_with_identity_map(vault_root: Path) -> int:
    """Merge duplicate persons using IdentityMap as ground truth.

    Falls back to existing fuzzy matching (dedup_draft_persons) for
    persons not in the identity map.
    """
    from vault.domain.identity_map import IdentityMap

    im = IdentityMap.load()
    if not im._entries:
        # No identity map — fall back to fuzzy-only dedup
        return dedup_draft_persons(vault_root)

    persons_dir = vault_root / "entities" / "persons"
    if not persons_dir.exists():
        return 0

    # Index existing files by canonical name
    canonical_files: dict[str, list[dict]] = {}
    for f in persons_dir.glob("*.md"):
        text = f.read_text(encoding="utf-8")
        end = text.find("---", 3)
        if end == -1:
            continue
        fm = yaml.safe_load(text[3:end]) or {}
        entity_name = fm.get("entity", f.stem)
        gh_login = fm.get("github_login")

        # Try resolution via identity map
        canonical = (
            im.resolve(entity_name)
            or im.resolve_by_github(gh_login or "")
            or im.resolve_by_trello_name(entity_name)
        )
        if canonical:
            canonical_files.setdefault(canonical, []).append({
                "file": f,
                "name": entity_name,
                "fm": fm,
            })

    # Merge duplicates within each canonical group
    merged = 0
    for canonical, entries in canonical_files.items():
        if len(entries) < 2:
            continue
        # Sort: prefer entries with more source_keys (richer)
        entries.sort(key=lambda e: len(e["fm"].get("source_keys", [])), reverse=True)
        keep = entries[0]
        for absorb in entries[1:]:
            # Merge frontmatter into keep
            keep_fm = keep["fm"]
            absorb_fm = absorb["fm"]
            keep_fm["entity"] = canonical
            # Union of source_keys
            keep_keys = set(keep_fm.get("source_keys", []) or [])
            absorb_keys = set(absorb_fm.get("source_keys", []) or [])
            keep_fm["source_keys"] = sorted(keep_keys | absorb_keys)
            # Merge other fields
            if not keep_fm.get("github_login") and absorb_fm.get("github_login"):
                keep_fm["github_login"] = absorb_fm["github_login"]
            if not keep_fm.get("email") and absorb_fm.get("email"):
                keep_fm["email"] = absorb_fm["email"]
            keep_fm["draft"] = False

            # Write merged keep file
            body = keep["file"].read_text(encoding="utf-8")
            end = body.find("---", 3)
            original_body = body[end + 3:]
            # Update title in body
            if original_body.lstrip("\n").startswith("# "):
                lines = original_body.lstrip("\n").split("\n")
                lines[0] = f"# {canonical}"
                original_body = "\n".join(lines)
            fm_text = yaml.dump(keep_fm, default_flow_style=False, sort_keys=False)
            _atomic_write(keep["file"], f"---\n{fm_text}---{original_body}")

            # Quarantine absorbed file
            quarantine = persons_dir / ".quarantine"
            quarantine.mkdir(exist_ok=True)
            dest = quarantine / absorb["file"].name
            if not dest.exists():
                absorb["file"].rename(dest)
            logger.info("Dedup (identity): merged '%s' into canonical '%s'", absorb["name"], canonical)
            merged += 1

    # Also run fuzzy dedup for any remaining unmapped drafts
    merged += dedup_draft_persons(vault_root)
    return merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_identity_merger.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Commit**

```bash
git add vault/ingest/crosslink_dedup.py vault/tests/test_identity_merger.py
git commit -m "feat(vault): extend crosslink_dedup with identity-map ground truth"
```

---

## Task 3: Wire Identity Map into Ingest Pipeline

**Files:**
- Modify: `vault/ingest/entity_writer.py` — use IdentityMap in `upsert_person`
- Modify: `vault/ingest/crosslink_resolver.py` — use IdentityMap for member/author resolution
- Test: extend `vault/tests/test_identity_map.py`

This connects the identity map to the actual ingest flow. The resolution chain becomes:
1. **IdentityMap** (exact YAML lookup) — authoritative ground truth
2. **`identity_resolution.resolve_identity()`** (signal-based) — for unmapped persons with github_login/email overlap
3. **`_find_existing_person_fuzzy()`** (name-based) — last resort fuzzy match

When `upsert_person` is called, it checks IdentityMap first. If the incoming name maps to a canonical, it uses that canonical name instead of creating a new entity. If no IdentityMap match, falls back to `resolve_identity()` for cross-source matching.

- [ ] **Step 1: Write the failing test**

```python
# Add to vault/tests/test_identity_map.py

def test_upsert_person_uses_identity_map(tmp_path):
    """upsert_person should redirect to canonical name via identity map."""
    from vault.ingest.entity_writer import upsert_person

    # Create a person entity with a Trello name
    entity = {
        "id_canonical": "person:tldv:lincoln",
        "display_name": "Lincoln",  # Trello alias
        "source_keys": ["trello-member:Lincoln"],
        "confidence": "medium",
    }
    path, written = upsert_person(entity, vault_root=tmp_path)

    # Should have been redirected to canonical name file
    text = path.read_text(encoding="utf-8")
    # Canonical name should be used, not the Trello alias
    assert "Lincoln Quinan Junior" in text or "lincolnqjunior" in text.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_identity_map.py::test_upsert_person_uses_identity_map -v`
Expected: FAIL (person created as "Lincoln" without redirect)

- [ ] **Step 3: Modify entity_writer.py upsert_person to use IdentityMap**

In `vault/ingest/entity_writer.py`, at the top of `upsert_person()`, add identity map lookup:

```python
# Add at top of upsert_person(), after entity_dir assignment:
    # --- Identity map lookup ---
    from vault.domain.identity_map import IdentityMap
    _identity_map = IdentityMap.load()
    canonical = _identity_map.resolve(new_name) or _identity_map.resolve_by_github(entity.get("github_login", ""))
    if canonical:
        entity["display_name"] = canonical
        entity.setdefault("entity", canonical)
        entity["id_canonical"] = f"person:canonical:{_slugify(canonical).lower().replace(' ', '-')}"
        new_name = canonical
```

Also add github_login lookup in `_find_existing_person_fuzzy` to match by canonical name.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_identity_map.py -v`
Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add vault/ingest/entity_writer.py vault/tests/test_identity_map.py
git commit -m "feat(vault): wire identity map into person upsert"
```

---

## Task 4: Run Dedup on Existing Vault — One-Shot Script

**Files:**
- Create: `vault/scripts/__init__.py`
- Create: `vault/scripts/dedup_persons.py`

A one-shot script that calls `dedup_with_identity_map()` from `crosslink_dedup.py` on the existing vault.

- [ ] **Step 0: Create `vault/scripts/__init__.py`**

```python
# vault/scripts/__init__.py
```

- [ ] **Step 1: Write the dedup script**

```python
# vault/scripts/dedup_persons.py
"""One-shot script to deduplicate existing person files in the vault.

Uses identity_map.yaml via crosslink_dedup.dedup_with_identity_map().
Run: python3 -m vault.scripts.dedup_persons
"""
from __future__ import annotations

import sys
from pathlib import Path


def main():
    workspace = Path(__file__).resolve().parents[2]
    vault_root = workspace / "memory" / "vault"

    # Ensure workspace is on path
    sys.path.insert(0, str(workspace))

    from vault.ingest.crosslink_dedup import dedup_with_identity_map
    merged = dedup_with_identity_map(vault_root)
    print(f"Done. {merged} duplicates merged.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the dedup script on the vault**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m vault.scripts.dedup_persons`
Expected: merges ~8 duplicate persons (lincolnqjunior+Lincoln, estevesm+esteves, victor-living+victor neves, marcioxrocha+marcio rocha, etc.)

- [ ] **Step 3: Verify results**

Run: `ls memory/vault/entities/persons/ | wc -l && ls memory/vault/entities/persons/.quarantine/ | wc -l`
Expected: persons/ should have ~9 unique persons, .quarantine/ should have ~8 absorbed files

- [ ] **Step 4: Rebuild index**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -c "from vault.ingest.index_manager import rebuild_index; from pathlib import Path; rebuild_index(Path('memory/vault'))"`

- [ ] **Step 5: Commit**

```bash
git add vault/scripts/ memory/vault/entities/persons/ memory/vault/index.md
git commit -m "fix(vault): deduplicate persons using identity map"
```

---

## Task 5: LLM Meeting Enrichment — Summary + Decisions

**Files:**
- Create: `vault/enrich/__init__.py`
- Create: `vault/enrich/llm_summarize.py`
- Test: `vault/tests/test_llm_summarize.py`

This module reads a meeting's transcript (from Supabase whisper_transcript field) and uses an LLM to extract a structured summary and decisions list.

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_llm_summarize.py
import pytest


@pytest.mark.skipif(
    not os.environ.get("OPENAI_API_KEY") and not os.environ.get("OMNIROUT_API_KEY"),
    reason="No LLM API key configured"
)
def test_extract_summary_from_transcript():
    """Given a transcript text, extract summary and decisions."""
    from unittest.mock import patch, MagicMock
    from vault.enrich.llm_summarize import extract_meeting_insights

    transcript = """
    Lincoln: Vamos discutir o deploy do voice commerce.
    Marcio: O deploy em UAT ficou estável, sem erros há 3 dias.
    Esteves: Podemos ir para prod na segunda.
    Lincoln: Ok, aprovado. Marcio, prepara o release notes.
    Marcio: Vou preparar até sexta.
    """

    # Mock LLM response
    mock_response = '{"summary": "Discussão sobre deploy do voice commerce em produção.", "decisions": ["Aprovar deploy do voice commerce em prod na segunda", "Marcio prepara release notes até sexta"]}'
    with patch("vault.enrich.llm_summarize._call_llm", return_value=mock_response):
        result = extract_meeting_insights(transcript)

    assert "summary" in result
    assert "decisions" in result
    assert isinstance(result["decisions"], list)
    assert len(result["decisions"]) >= 1


def test_extract_summary_empty_transcript():
    from vault.enrich.llm_summarize import extract_meeting_insights
    result = extract_meeting_insights("")
    assert result["summary"] == ""
    assert result["decisions"] == []


def test_extract_summary_json_parse_fallback():
    """Test JSON extraction from markdown code block."""
    from unittest.mock import patch
    from vault.enrich.llm_summarize import extract_meeting_insights

    transcript = "Some discussion text."
    mock_response = '```json\n{"summary": "Test summary", "decisions": ["dec1"]}\n```'
    with patch("vault.enrich.llm_summarize._call_llm", return_value=mock_response):
        result = extract_meeting_insights(transcript)
    assert result["summary"] == "Test summary"
    assert result["decisions"] == ["dec1"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_llm_summarize.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Write llm_summarize.py implementation**

```python
# vault/enrich/llm_summarize.py
"""LLM-based meeting enrichment — extract summary and decisions from transcript.

Uses OpenAI-compatible API (OmniRoute) to process transcripts.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """Você é um assistente que analisa transcrições de reuniões de trabalho.
Dado o transcript de uma reunião, extraia:

1. **Resumo** (2-4 parágrafos): O que foi discutido, pontos principais, acordos.
2. **Decisões** (lista): Cada decisão tomada, com responsável quando mencionado.

Responda em JSON:
{
  "summary": "texto do resumo...",
  "decisions": ["decisão 1", "decisão 2", ...]
}

Seja objetivo e técnico. Responda em português."""

_USER_TEMPLATE = """Analise esta transcrição de reunião:

---
{transcript}
---

Extraia o resumo e as decisões em JSON."""


def _call_llm(messages: list[dict], model: str | None = None) -> str:
    """Call LLM via OpenAI-compatible API."""
    import requests

    base_url = os.environ.get("OPENAI_BASE_URL", "http://localhost:20128/v1")
    api_key = os.environ.get("OPENAI_API_KEY", os.environ.get("OMNIROUT_API_KEY", "sk-placeholder"))

    model = model or os.environ.get("VAULT_ENRICH_MODEL", "omniroute/PremiumFirst")

    resp = requests.post(
        f"{base_url}/chat/completions",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.3,
            "max_tokens": 2000,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def extract_meeting_insights(
    transcript: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Extract summary and decisions from a meeting transcript.

    Args:
        transcript: Full transcript text.
        model: Optional model override.

    Returns:
        {"summary": str, "decisions": list[str]}
    """
    if not transcript or not transcript.strip():
        return {"summary": "", "decisions": []}

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": _USER_TEMPLATE.format(transcript=transcript[:8000])},
    ]

    try:
        raw = _call_llm(messages, model=model)
    except Exception as exc:
        logger.error("LLM call failed: %s", exc)
        return {"summary": "", "decisions": [], "error": str(exc)}

    # Parse JSON from response
    try:
        # Try direct parse
        result = json.loads(raw)
        return {
            "summary": result.get("summary", ""),
            "decisions": result.get("decisions", []),
        }
    except json.JSONDecodeError:
        # Try to extract JSON from markdown code block
        import re
        json_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if json_match:
            try:
                result = json.loads(json_match.group(1))
                return {
                    "summary": result.get("summary", ""),
                    "decisions": result.get("decisions", []),
                }
            except json.JSONDecodeError:
                pass
        # Fallback: use raw text as summary
        return {"summary": raw[:500], "decisions": []}


def enrich_meeting_file(meeting_path: str | Path, transcript: str, model: str | None = None) -> bool:
    """Enrich a meeting markdown file with LLM-extracted summary and decisions.

    Replaces the placeholder comments in ## Resumo and ## Decisões sections.

    Returns True if enrichment was applied.
    """
    import yaml
    from pathlib import Path

    path = Path(meeting_path)
    if not path.exists():
        return False

    insights = extract_meeting_insights(transcript, model=model)
    if not insights.get("summary") and not insights.get("decisions"):
        return False

    text = path.read_text(encoding="utf-8")

    # Replace ## Resumo section
    import re
    summary_block = insights["summary"]
    text = re.sub(
        r"(## Resumo\n\n)(.*?)(\n\n## Decisões)",
        lambda m: m.group(1) + summary_block + "\n" + m.group(3),
        text,
        flags=re.DOTALL,
    )

    # Replace ## Decisões section
    if insights.get("decisions"):
        decisions_md = "\n".join(f"- {d}" for d in insights["decisions"])
        text = re.sub(
            r"(## Decisões\n\n)(.*?)(\n\n## )",
            lambda m: m.group(1) + decisions_md + "\n" + m.group(3),
            text,
            flags=re.DOTALL,
        )

    path.write_text(text, encoding="utf-8")
    return True
```

- [ ] **Step 4: Create `vault/enrich/__init__.py`**

```python
# vault/enrich/__init__.py
```

- [ ] **Step 5: Run tests**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_llm_summarize.py -v`
Expected: tests PASS (empty transcript test passes immediately; full test calls LLM)

- [ ] **Step 6: Commit**

```bash
git add vault/enrich/ vault/tests/test_llm_summarize.py
git commit -m "feat(vault): add LLM meeting enrichment for summaries and decisions"
```

---

## Task 6: Enrichment Context Relevance Filter

**Files:**
- Create: `vault/enrich/relevance_filter.py`
- Test: `vault/tests/test_relevance_filter.py`

Filters the `enrichment_context` (Trello cards, GitHub PRs) attached to meetings so only items relevant to the meeting's topic/project are included.

- [ ] **Step 1: Write the failing test**

```python
# vault/tests/test_relevance_filter.py
from vault.enrich.relevance_filter import filter_enrichment_context


def test_filter_cards_by_board_relevance():
    """Only cards from boards matching the meeting project should be included."""
    context = {
        "trello": {
            "cards": [
                {"id": "1", "name": "Voice deploy", "board_id": "66e99655"},  # BAT board
                {"id": "2", "name": "Delphos OCR setup", "board_id": "6697cdb0"},  # Delphos board
                {"id": "3", "name": "Daily meeting card", "board_id": "66e99655"},  # BAT board
            ]
        }
    }

    # Meeting about BAT should only get BAT cards
    filtered = filter_enrichment_context(context, meeting_title="Status Kaba - BAT - BOT")
    bat_cards = filtered["trello"]["cards"]
    assert len(bat_cards) == 2
    assert all(c["board_id"] == "66e99655" for c in bat_cards)


def test_filter_keeps_all_when_no_match():
    """If no project detected, keep all cards (conservative)."""
    context = {
        "trello": {
            "cards": [
                {"id": "1", "name": "Card A", "board_id": "aaa"},
                {"id": "2", "name": "Card B", "board_id": "bbb"},
            ]
        }
    }
    filtered = filter_enrichment_context(context, meeting_title="Random Meeting")
    assert len(filtered["trello"]["cards"]) == 2  # keeps all
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_relevance_filter.py -v`
Expected: FAIL

- [ ] **Step 3: Write relevance_filter.py**

```python
# vault/enrich/relevance_filter.py
"""Filter enrichment_context to only items relevant to the meeting's project.

Uses meeting title → project mapping and board_id → project mapping
to determine relevance.
"""
from __future__ import annotations

import re
from typing import Any

# Meeting title pattern → relevant board_ids
_PROJECT_BOARD_MAP = {
    "BAT": {
        "patterns": [r"Status\s+Kaba", r"BAT", r"Conecta.?Bot", r"voice", r"Voice"],
        "board_ids": {"66e99655f8e85b6698d3d784", "69a086a99bb2eb087f43ec75"},
    },
    "Delphos": {
        "patterns": [r"Delphos", r"Robô.*OCR", r"Elcano"],
        "board_ids": {"6697cdb0b388dea00a594901", "6964f88f5b00feaf4078988d"},
    },
    "B3": {
        "patterns": [r"Daily.*Operações.*B3", r"B3.*Billing", r"ECB"],
        "board_ids": {"5d85184c0c352d33748609f0", "60f058aa0bebde2f6e4e4b9c", "660ff54fc58cbcea05710f15"},
    },
    "Imobi": {
        "patterns": [r"Cadência\s+4D\s+imobi", r"4D\s+[Ii]mobi"],
        "board_ids": set(),
    },
}


def _detect_project(title: str) -> str | None:
    """Detect which project a meeting title refers to."""
    for project, config in _PROJECT_BOARD_MAP.items():
        for pattern in config["patterns"]:
            if re.search(pattern, title, re.IGNORECASE):
                return project
    return None


def filter_enrichment_context(
    context: dict[str, Any],
    meeting_title: str = "",
    max_cards: int = 20,
) -> dict[str, Any]:
    """Filter enrichment_context to only relevant items.

    If no project is detected from the title, returns all items (conservative).
    If a project is detected, only includes cards/PRs from matching boards/repos.
    """
    project = _detect_project(meeting_title)
    if not project:
        # Conservative: keep everything
        return context

    board_ids = _PROJECT_BOARD_MAP.get(project, {}).get("board_ids", set())
    filtered = dict(context)

    if "trello" in filtered and board_ids:
        cards = filtered["trello"].get("cards", [])
        filtered["trello"] = {
            **filtered["trello"],
            "cards": [c for c in cards if c.get("board_id") in board_ids][:max_cards],
        }

    return filtered
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_relevance_filter.py -v`
Expected: 2 tests PASS

- [ ] **Step 5: Wire into external_ingest.py**

In `vault/ingest/external_ingest.py`, in the meeting upsert loop, before writing the meeting entity, add:

```python
    # Filter enrichment context to relevant items only
    from vault.enrich.relevance_filter import filter_enrichment_context
    ec = entity.get("enrichment_context", {})
    if ec:
        entity["enrichment_context"] = filter_enrichment_context(ec, meeting_title=entity.get("title", ""))
```

- [ ] **Step 6: Commit**

```bash
git add vault/enrich/relevance_filter.py vault/tests/test_relevance_filter.py vault/ingest/external_ingest.py
git commit -m "feat(vault): filter enrichment context by meeting project relevance"
```

---

## Task 7: Lint-and-Fix Auto-Correction

**Files:**
- Create: `vault/lint/auto_fix.py`
- Test: `vault/tests/test_lint.py` (extend existing)

Extends the vault-lint scanner to auto-fix common issues: remove orphan links, update stale index entries, and repair broken frontmatter.

- [ ] **Step 1: Write the failing test**

```python
# Add to vault/tests/test_lint.py

def test_auto_fix_removes_orphan_wikilinks(tmp_path):
    """Auto-fix should remove [[wiki-links]] pointing to non-existent files."""
    from vault.lint.auto_fix import auto_fix_orphan_links

    vault = tmp_path / "vault"
    entities = vault / "entities" / "meetings"
    entities.mkdir(parents=True)

    # Meeting file referencing a non-existent person
    meeting = entities / "test-meeting.md"
    meeting.write_text(
        "---\ntype: meeting\n---\n\n"
        "# Test\n\n"
        "## Participantes\n\n"
        "- [[Nonexistent Person]]\n"
        "- [[Existing Person]]\n"
    )

    # Create the existing person
    persons = vault / "entities" / "persons"
    persons.mkdir(parents=True)
    (persons / "Existing Person.md").write_text("---\ntype: person\n---\n\n# Existing Person\n")

    fixes = auto_fix_orphan_links(vault)
    assert fixes["orphan_links_removed"] >= 1
    text = meeting.read_text()
    assert "[[Nonexistent Person]]" not in text
    assert "[[Existing Person]]" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_lint.py::test_auto_fix_removes_orphan_wikilinks -v`
Expected: FAIL

- [ ] **Step 3: Write auto_fix.py**

```python
# vault/lint/auto_fix.py
"""Auto-fix common vault issues detected by lint scanner."""
from __future__ import annotations

import re
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _all_existing_slugs(vault_root: Path) -> set[str]:
    """Collect all existing entity filenames (without .md) as a slug set."""
    slugs = set()
    for entities_sub in ["meetings", "persons", "projects", "cards", "prs"]:
        d = vault_root / "entities" / entities_sub
        if d.exists():
            for f in d.glob("*.md"):
                slugs.add(f.stem)
    return slugs


def auto_fix_orphan_links(vault_root: Path) -> dict[str, Any]:
    """Remove [[wiki-links]] pointing to non-existent entity files.

    Scans all .md files in the vault and removes links to missing entities.
    """
    existing = _all_existing_slugs(vault_root)
    fixes = {"orphan_links_removed": 0, "files_modified": 0}

    for md_file in vault_root.rglob("*.md"):
        if ".quarantine" in str(md_file) or ".cursors" in str(md_file):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
        except OSError:
            continue

        modified = False
        # Find all [[wiki-links]]
        def _replace_link(m: re.Match) -> str:
            nonlocal modified
            slug = m.group(1).strip()
            # Check if target exists
            # Try direct match and date+slug match
            found = slug in existing
            if not found:
                # Try matching just the title part after date
                parts = slug.split(" ", 1)
                if len(parts) > 1 and parts[0].count("-") == 2:
                    # Looks like "2026-03-24 Title"
                    title_slug = parts[1] if len(parts) > 1 else slug
                    found = title_slug in existing
            if found:
                return m.group(0)
            modified = True
            fixes["orphan_links_removed"] += 1
            return ""

        new_text = re.sub(r"\[\[([^\]]+)\]\]", _replace_link, text)

        if modified:
            # Clean up blank lines left by removals
            new_text = re.sub(r"\n{3,}", "\n\n", new_text)
            md_file.write_text(new_text, encoding="utf-8")
            fixes["files_modified"] += 1

    return fixes
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m pytest vault/tests/test_lint.py::test_auto_fix_removes_orphan_wikilinks -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add vault/lint/auto_fix.py vault/tests/test_lint.py
git commit -m "feat(vault): add auto-fix for orphan wiki-links"
```

---

## Task 8: Wire Everything into the Ingest Cron

**Files:**
- Modify: `vault/crons/vault_ingest_cron.py`

Adds LLM enrichment and auto-fix as stages in the regular vault-ingest cron job.

- [ ] **Step 1: Add enrichment stage to vault_ingest_cron.py**

After the existing `run_external_ingest()` call, add:

```python
    # Stage: LLM enrichment for meetings without summaries
    try:
        from vault.enrich.llm_summarize import enrich_meeting_file
        from vault.ingest.meeting_ingest import fetch_meetings_from_supabase

        meetings = fetch_meetings_from_supabase(days=7)
        enriched = 0
        for raw in meetings:
            title = raw.get("name", "")
            transcript = raw.get("whisper_transcript", "")
            if not transcript or not transcript.strip():
                continue
            # Find corresponding meeting file
            started = raw.get("created_at", "")[:10]
            slug = title.replace("/", " - ")[:60]
            pattern = f"{started} {slug}.md" if started else f"{slug}.md"
            matches = list((vault_root / "entities" / "meetings").glob(pattern))
            if not matches:
                continue
            mf = matches[0]
            text = mf.read_text(encoding="utf-8")
            # Skip if already enriched (no placeholder comment)
            if "<!-- Enriquecimento TLDV" not in text:
                continue
            if enrich_meeting_file(mf, transcript):
                enriched += 1
        result["meetings_enriched"] = enriched
    except Exception as exc:
        print(f"[WARN] LLM enrichment failed: {exc}", file=sys.stderr)
```

- [ ] **Step 2: Add auto-fix stage**

```python
    # Stage: Auto-fix orphan links
    try:
        from vault.lint.auto_fix import auto_fix_orphan_links
        fix_result = auto_fix_orphan_links(vault_root)
        result["auto_fix"] = fix_result
    except Exception as exc:
        print(f"[WARN] Auto-fix failed: {exc}", file=sys.stderr)
```

- [ ] **Step 3: Test the cron end-to-end**

Run: `cd /home/lincoln/.openclaw/workspace-livy-memory && python3 -m vault.crons.vault_ingest_cron 2>&1`
Expected: runs successfully with enrichment counts in output

- [ ] **Step 4: Commit**

```bash
git add vault/crons/vault_ingest_cron.py
git commit -m "feat(vault): add LLM enrichment and auto-fix to ingest cron"
```

---

## Summary

| Task | What | Effort |
|---|---|---|
| 1 | Identity Map YAML + Loader | 30 min |
| 2 | Extend crosslink_dedup with identity map | 30 min |
| 3 | Wire into ingest pipeline (compose with identity_resolution) | 20 min |
| 4 | One-shot dedup on existing vault | 15 min |
| 5 | LLM Meeting Enrichment (with mocked tests) | 45 min |
| 6 | Enrichment Context Filter | 30 min |
| 7 | Lint-and-Fix Auto-Correction | 30 min |
| 8 | Wire into Ingest Cron | 20 min |
| **Total** | | **~3.5h** |
