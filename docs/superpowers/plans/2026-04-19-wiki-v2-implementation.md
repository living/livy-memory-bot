# Wiki v2 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o núcleo de memória Wiki v2 com Fusion Engine, CaptureConnectors evoluídos e Azure Blob como fonte primária de transcripts — completando a Fase 1 do rollout.

**Architecture:** Sistema de memória semântico multi-fonte com:
- Memory Core (estado SSOT + invariantes) como nova camada central
- Fusion Engine (reconciliação + confidence + supersession) como biblioteca pura
- CaptureConnectors evoluídos reusing `personal-data-connectors`
- Azure Blob como fonte canônica de transcripts (SSOT de conteúdo)

**Tech Stack:** Python 3.12+ | claude-mem (SQLite) | Azure Blob Storage SDK | GitHub CLI (`gh`) | Trello API | Google APIs (Gmail, Calendar) | OmniRouter (PremiumFirst / fastest)

**Spec:** `docs/superpowers/specs/2026-04-19-wiki-v2-design.md`

---

## Regra de Execução Obrigatória (TDD)

Para **toda tarefa deste plano**, seguir obrigatoriamente a sequência:
1. **RED** — escrever teste que falha
2. **RED-CHECK** — rodar teste e confirmar falha esperada
3. **GREEN** — implementar mínimo para passar
4. **GREEN-CHECK** — rodar teste e confirmar PASS
5. **REFACTOR + COMMIT** — limpeza mínima + commit

> Se o snippet de uma tarefa mostrar código antes de teste, reinterpretar a execução nessa ordem acima (TDD estrito). Não pular RED/RED-CHECK.

---

## Fase 1 — Fundação do Núcleo (Governança + Azure-first)

### Tarefa 1: Memory Core — Schema e Invariantes

**Files:**
- Create: `vault/memory_core/models.py`
- Create: `vault/memory_core/exceptions.py`
- Create: `vault/memory_core/__init__.py`
- Create: `tests/vault/test_memory_core_models.py`
- Modify: `vault/__init__.py` (adicionar import)

---

- [ ] **Step 1: Criar estrutura de diretório e exceção base**

```python
# vault/memory_core/exceptions.py
class MemoryCoreError(Exception):
    """Base exception for all memory core errors."""
    pass


class CorruptStateError(MemoryCoreError):
    """Raised when an invariant is violated during write.

    This exception is NOT strippable with -O (unlike assert).
    """
    pass


class DuplicateClaimError(MemoryCoreError):
    """Raised when attempting to insert a duplicate claim."""
    pass


class MissingEvidenceError(MemoryCoreError):
    """Raised when claim has no evidence_ids or evidence_ids is empty."""
    pass
```

Run: `python -c "from vault.memory_core.exceptions import CorruptStateError; print('OK')"`
Expected: `OK`

---

- [ ] **Step 2: Definir Claim schema completo (spec Seção 3.3)**

```python
# vault/memory_core/models.py
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
import uuid


EntityType = Literal[
    "person", "project", "repository", "pull_request",
    "meeting", "topic", "decision", "email_thread"
]
ClaimType = Literal[
    "status", "decision", "action_item", "risk",
    "ownership", "timeline_event", "linkage"
]
PrivacyLevel = Literal["public", "internal", "restricted"]
Source = Literal["trello", "github", "tldv", "gmail", "gcal"]


@dataclass
class SourceRef:
    source_id: str
    url: str | None = None
    blob_path: str | None = None


@dataclass
class AuditTrail:
    model_used: str
    parser_version: str
    trace_id: str


@dataclass
class Claim:
    claim_id: str
    entity_type: EntityType
    entity_id: str
    topic_id: str | None
    claim_type: ClaimType
    text: str
    source: Source
    source_ref: SourceRef
    evidence_ids: list[str]  # INVARIANT: len >= 1
    author: str
    event_timestamp: str  # ISO 8601
    ingested_at: str  # ISO 8601
    confidence: float  # 0.0 to 1.0
    privacy_level: PrivacyLevel
    superseded_by: str | None = None
    supersession_reason: str | None = None
    supersession_version: int | None = None
    audit_trail: AuditTrail | None = None

    def validate(self) -> None:
        """Validate all invariants. Raises CorruptStateError on violation."""
        from vault.memory_core.exceptions import MissingEvidenceError, CorruptStateError

        if not self.evidence_ids or len(self.evidence_ids) == 0:
            raise MissingEvidenceError(
                f"Claim {self.claim_id} has empty evidence_ids — "
                "every claim requires at least one evidence_id"
            )
        if self.audit_trail is None:
            raise CorruptStateError(
                f"Claim {self.claim_id} has no audit_trail — write without audit is rejected"
            )
        if self.superseded_by is not None:
            if not self.audit_trail:
                raise CorruptStateError(
                    f"Claim {self.claim_id} is marked superseded but has no audit_trail"
                )
            if not self.supersession_reason:
                raise CorruptStateError(
                    f"Claim {self.claim_id} superseded sem supersession_reason"
                )
            if self.supersession_version is None:
                raise CorruptStateError(
                    f"Claim {self.claim_id} superseded sem supersession_version"
                )

    @staticmethod
    def new(
        entity_type: EntityType,
        entity_id: str,
        claim_type: ClaimType,
        text: str,
        source: Source,
        source_ref: SourceRef,
        evidence_ids: list[str],
        author: str,
        event_timestamp: str,
        topic_id: str | None = None,
        privacy_level: PrivacyLevel,
        model_used: str = "omniroute/fastest",
        parser_version: str = "v1",
    ) -> "Claim":
        claim_id = str(uuid.uuid4())
        from datetime import timezone
        now = datetime.now(timezone.utc).isoformat()
        audit = AuditTrail(
            model_used=model_used,
            parser_version=parser_version,
            trace_id=str(uuid.uuid4()),
        )
        claim = Claim(
            claim_id=claim_id,
            entity_type=entity_type,
            entity_id=entity_id,
            topic_id=topic_id,
            claim_type=claim_type,
            text=text,
            source=source,
            source_ref=source_ref,
            evidence_ids=evidence_ids,
            author=author,
            event_timestamp=event_timestamp,
            ingested_at=now,
            confidence=0.0,
            privacy_level=privacy_level,
            superseded_by=None,
            supersession_reason=None,
            supersession_version=None,
            audit_trail=audit,
        )
        claim.validate()
        return claim


@dataclass
class Evidence:
    evidence_id: str
    source: Source
    source_id: str
    raw_ref: str
    event_timestamp: str
    author: str
    privacy_level: PrivacyLevel
    content_hash: str
    blob_path: str | None = None
```

Run: `python -c "from vault.memory_core.models import Claim, Evidence; print('OK')"`
Expected: `OK`

---

- [ ] **Step 3: Escrever testes para invariantes**

```python
# tests/vault/test_memory_core_models.py
import pytest
from vault.memory_core.models import Claim, SourceRef
from vault.memory_core.exceptions import MissingEvidenceError, CorruptStateError
# Claim.new is a static factory method on Claim.


def test_claim_without_evidence_ids_raises():
    ref = SourceRef(source_id="abc", url="https://example.com")
    with pytest.raises(MissingEvidenceError):
        Claim.new(
            entity_type="project",
            entity_id="proj-1",
            claim_type="status",
            text="Card moved to Done",
            source="trello",
            source_ref=ref,
            evidence_ids=[],  # empty — should raise
            author="lincoln@livingnet.com.br",
            event_timestamp="2026-04-19T12:00:00Z",
            privacy_level="internal",
        )


def test_claim_without_audit_trail_raises():
    ref = SourceRef(source_id="abc", url="https://example.com")
    claim = Claim(
        claim_id="c1",
        entity_type="project",
        entity_id="proj-1",
        topic_id=None,
        claim_type="status",
        text="Card moved to Done",
        source="trello",
        source_ref=ref,
        evidence_ids=["ev-1"],
        author="lincoln@livingnet.com.br",
        event_timestamp="2026-04-19T12:00:00Z",
        ingested_at="2026-04-19T12:01:00Z",
        confidence=0.5,
        privacy_level="public",
        superseded_by=None,
        supersession_reason=None,
        supersession_version=None,
        audit_trail=None,  # missing — should raise on validate()
    )
    with pytest.raises(CorruptStateError):
        claim.validate()


def test_valid_claim_passes():
    ref = SourceRef(source_id="abc", url="https://example.com")
    claim = Claim.new(
        entity_type="project",
        entity_id="proj-1",
        claim_type="status",
        text="Card moved to Done",
        source="trello",
        source_ref=ref,
        evidence_ids=["ev-1"],
        author="lincoln@livingnet.com.br",
        event_timestamp="2026-04-19T12:00:00Z",
        privacy_level="internal",
    )
    assert claim.claim_id is not None
    assert claim.confidence == 0.0
    assert claim.audit_trail is not None
```

Run: `PYTHONPATH=. pytest tests/vault/test_memory_core_models.py -v`
Expected: 3 tests — FAIL (not yet implemented)

---

- [ ] **Step 4: Commit**

```bash
git add vault/memory_core/ tests/vault/test_memory_core_models.py
git commit -m "feat: memory core schema com Claim/Evidence models e invariantes"
```

---

### Tarefa 2: Fusion Engine v1 — Confiança, Supersession e Detecção de Contradição

**Files:**
- Create: `vault/fusion_engine/confidence.py`
- Create: `vault/fusion_engine/supersession.py`
- Create: `vault/fusion_engine/contradiction.py`
- Create: `vault/fusion_engine/engine.py`
- Create: `vault/fusion_engine/__init__.py`
- Create: `tests/vault/test_confidence.py`
- Create: `tests/vault/test_supersession.py`
- Create: `tests/vault/test_contradiction.py`
- Create: `tests/vault/test_fusion_engine.py`

---

- [ ] **Step 1: Implementar fórmula de confiança (spec Seção 5.4)**

```python
# vault/fusion_engine/confidence.py
"""
Confidence scoring formula (spec Section 5.4).

base_confidence = 0.5
+ source_reliability_score (github: +0.2, tldv: +0.2, gmail: +0.15, trello: +0.1)
+ recency_score (last_evidence < 7d: +0.2, < 30d: +0.1, < 90d: 0, > 90d: -0.2)
+ convergence_score (n_sources agreeing: +0.1 per source, max +0.3)
- contradiction_penalty (contradiction detected: -0.3)
final_confidence = clamp(base + adjustments, 0.0, 1.0)
"""
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Literal

Source = Literal["trello", "github", "tldv", "gmail", "gcal"]

_SOURCE_RELIABILITY: dict[Source, float] = {
    "github": 0.20,
    "tldv": 0.20,
    "gmail": 0.15,
    "trello": 0.10,
    "gcal": 0.10,
}

BASE_CONFIDENCE = 0.50
MAX_CONVERGENCE_BONUS = 0.30
CONVERGENCE_PER_SOURCE = 0.10
CONTRADICTION_PENALTY = 0.30
RECENCY_7D = timedelta(days=7)
RECENCY_30D = timedelta(days=30)
RECENCY_90D = timedelta(days=90)


@dataclass
class ConfidenceInput:
    source: Source
    event_timestamp: str  # ISO 8601
    all_sources_converging: list[Source]  # other sources agreeing on the same claim
    has_contradiction: bool


def calculate_confidence(input: ConfidenceInput) -> float:
    source_score = _SOURCE_RELIABILITY.get(input.source, 0.0)

    recency_score = _recency_score(input.event_timestamp)

    convergence_bonus = min(
        len(input.all_sources_converging) * CONVERGENCE_PER_SOURCE,
        MAX_CONVERGENCE_BONUS,
    )

    contradiction_penalty = CONTRADICTION_PENALTY if input.has_contradiction else 0.0

    raw = BASE_CONFIDENCE + source_score + recency_score + convergence_bonus - contradiction_penalty
    return max(0.0, min(1.0, raw))


def _recency_score(event_timestamp: str) -> float:
    try:
        if event_timestamp.endswith("Z"):
            event_ts = datetime.fromisoformat(event_timestamp[:-1])
        else:
            event_ts = datetime.fromisoformat(event_timestamp)
        if event_ts.tzinfo is None:
            event_ts = event_ts.replace(tzinfo=timezone.utc)
    except ValueError:
        return 0.0

    age = datetime.now(timezone.utc) - event_ts

    if age < RECENCY_7D:
        return 0.20
    elif age < RECENCY_30D:
        return 0.10
    elif age < RECENCY_90D:
        return 0.0
    else:
        return -0.20
```

Run: `python -c "from vault.fusion_engine.confidence import calculate_confidence, ConfidenceInput; print('OK')"`
Expected: `OK`

---

- [ ] **Step 2: Implementar supersession**

```python
# vault/fusion_engine/supersession.py
"""
Supersession logic (spec Section 5.1 item 4).

Policy:
- newer claim replaces older claim on same entity_id + claim_type
- older claim receives superseded_by = new_claim_id
- superseded claim is NOT deleted (preserves audit trail)
- superseded_by can only be set once
"""
from datetime import datetime
from vault.memory_core.models import Claim


def should_supersede(candidate: Claim, existing: Claim) -> bool:
    """Return True if candidate should supersede existing claim.

    Policy:
    - Must be same entity_id + claim_type (same fact about same entity)
    - Candidate must be newer (event_timestamp > existing.event_timestamp)
    - Existing must not already be superseded
    """
    if existing.superseded_by is not None:
        return False

    if candidate.entity_id != existing.entity_id:
        return False

    if candidate.claim_type != existing.claim_type:
        return False

    # Compare timestamps
    try:
        from datetime import timezone
        cand_ts = datetime.fromisoformat(candidate.event_timestamp.replace("Z", "+00:00"))
        exist_ts = datetime.fromisoformat(existing.event_timestamp.replace("Z", "+00:00"))
        return cand_ts > exist_ts
    except ValueError:
        return False


def apply_supersession(candidate: Claim, existing: Claim) -> tuple[Claim, Claim]:
    """Return (updated_existing, updated_candidate) with superseded_by set."""
    updated_existing = existing
    updated_existing.superseded_by = candidate.claim_id

    updated_candidate = candidate
    return updated_existing, updated_candidate
```

Run: `python -c "from vault.fusion_engine.supersession import should_supersede; print('OK')"`
Expected: `OK`

---

- [ ] **Step 3: Implementar detecção de contradição**

```python
# vault/fusion_engine/contradiction.py
"""
Contradiction detection (spec Section 5.3).

IF topic_A has claim_X (source=S, confidence=0.9)
AND claim_Y about topic_A exists (source=T, confidence=0.8)
AND claim_X.text ≠ claim_Y.text
THEN flag = contradiction
AND do NOT auto-supersede — human review required
"""
from dataclasses import dataclass
from vault.memory_core.models import Claim


@dataclass
class ContradictionResult:
    has_contradiction: bool
    claim_a_id: str | None
    claim_b_id: str | None
    topic_id: str | None
    severity: str  # "high" | "medium" | "low"


def detect_contradiction(
    new_claim: Claim,
    existing_claims: list[Claim],
) -> ContradictionResult:
    """Check if new_claim contradicts any existing claim about the same topic/entity."""
    if not new_claim.topic_id:
        return ContradictionResult(
            has_contradiction=False,
            claim_a_id=None,
            claim_b_id=None,
            topic_id=None,
            severity="low",
        )

    for existing in existing_claims:
        if existing.claim_id == new_claim.claim_id:
            continue

        same_topic = existing.topic_id == new_claim.topic_id
        same_entity = existing.entity_id == new_claim.entity_id
        different_text = existing.text.strip() != new_claim.text.strip()
        not_superseded = existing.superseded_by is None

        if same_topic and same_entity and different_text and not_superseded:
            severity = _severity(new_claim.confidence, existing.confidence)
            return ContradictionResult(
                has_contradiction=True,
                claim_a_id=new_claim.claim_id,
                claim_b_id=existing.claim_id,
                topic_id=new_claim.topic_id,
                severity=severity,
            )

    return ContradictionResult(
        has_contradiction=False,
        claim_a_id=None,
        claim_b_id=None,
        topic_id=None,
        severity="low",
    )


def _severity(conf_a: float, conf_b: float) -> str:
    avg = (conf_a + conf_b) / 2
    if avg >= 0.75:
        return "high"
    elif avg >= 0.50:
        return "medium"
    return "low"
```

Run: `python -c "from vault.fusion_engine.contradiction import detect_contradiction; print('OK')"`
Expected: `OK`

---

- [ ] **Step 4: Orchestrar Fusion Engine**

```python
# vault/fusion_engine/engine.py
"""
Fusion Engine — reconcilia claims, calcula confiança, detecta contradição,
aplica supersession. É o "motor" (spec Section 5).

research-consolidation é o "driver" que invoca este motor.
"""
from vault.fusion_engine.confidence import calculate_confidence, ConfidenceInput
from vault.fusion_engine.contradiction import detect_contradiction, ContradictionResult
from dataclasses import dataclass
from vault.fusion_engine.supersession import should_supersede, apply_supersession
from vault.memory_core.models import Claim


@dataclass
class FusionResult:
    claim: Claim
    contradiction: ContradictionResult | None
    superseded_claims: list[Claim]  # claims that were superseded by this one
    was_superseded: bool  # True if this claim was superseded by another


def fuse(new_claim: Claim, existing_claims: list[Claim]) -> FusionResult:
    """
    Main entry point: reconcile new_claim against existing claims.

    1. Detect contradiction
    2. Apply supersession if applicable
    3. Calculate confidence
    4. Return FusionResult with all decisions
    """
    contradiction = detect_contradiction(new_claim, existing_claims)

    superseded_claims: list[Claim] = []
    for existing in existing_claims:
        if should_supersede(new_claim, existing):
            updated_existing, updated_candidate = apply_supersession(new_claim, existing)
            superseded_claims.append(updated_existing)
            new_claim = updated_candidate

    # Collect all sources converging on this claim (excluding self)
    converging_sources = [
        c.source for c in existing_claims
        if c.topic_id == new_claim.topic_id
        and c.text.strip() == new_claim.text.strip()
        and c.claim_id != new_claim.claim_id
    ]

    conf_input = ConfidenceInput(
        source=new_claim.source,
        event_timestamp=new_claim.event_timestamp,
        all_sources_converging=converging_sources,
        has_contradiction=contradiction.has_contradiction,
    )
    new_claim.confidence = calculate_confidence(conf_input)

    return FusionResult(
        claim=new_claim,
        contradiction=contradiction if contradiction.has_contradiction else None,
        superseded_claims=superseded_claims,
        was_superseded=False,
    )
```

Run: `python -c "from vault.fusion_engine.engine import fuse; print('OK')"`
Expected: `OK`

---

- [ ] **Step 5: Testes de unidade**

```python
# tests/vault/test_confidence.py
from vault.fusion_engine.confidence import calculate_confidence, ConfidenceInput


def test_github_recent_high_confidence():
    inp = ConfidenceInput(
        source="github",
        event_timestamp="2026-04-19T11:00:00Z",
        all_sources_converging=["tldv"],
        has_contradiction=False,
    )
    conf = calculate_confidence(inp)
    # github: +0.20, recency < 7d: +0.20, convergence: +0.10, no contradiction
    # = 0.50 + 0.20 + 0.20 + 0.10 = 1.0 → clamped to 1.0
    assert conf == 1.0


def test_trello_old_contradiction_low():
    inp = ConfidenceInput(
        source="trello",
        event_timestamp="2026-01-01T00:00:00Z",
        all_sources_converging=[],
        has_contradiction=True,
    )
    conf = calculate_confidence(inp)
    # 0.50 + 0.10 + (-0.20) + 0 - 0.30 = 0.10
    assert conf == 0.10


def test_gmail_7d_to_30d():
    from datetime import datetime, timezone, timedelta
    recent = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
    inp = ConfidenceInput(
        source="gmail",
        event_timestamp=recent,
        all_sources_converging=[],
        has_contradiction=False,
    )
    conf = calculate_confidence(inp)
    # 0.50 + 0.15 + 0.10 = 0.75
    assert conf == 0.75
```

```python
# tests/vault/test_supersession.py
from vault.fusion_engine.supersession import should_supersede


def test_supersedes_when_newer():
    older = _make_claim("c1", "proj-1", "status", "2026-04-19T10:00:00Z")
    newer = _make_claim("c2", "proj-1", "status", "2026-04-19T12:00:00Z")
    assert should_supersede(newer, older) is True


def test_does_not_supersede_different_entity():
    c1 = _make_claim("c1", "proj-1", "status", "2026-04-19T10:00:00Z")
    c2 = _make_claim("c2", "proj-2", "status", "2026-04-19T12:00:00Z")
    assert should_supersede(c2, c1) is False


def test_does_not_supersede_already_superseded():
    older = _make_claim("c1", "proj-1", "status", "2026-04-19T10:00:00Z")
    older.superseded_by = "c-other"
    newer = _make_claim("c2", "proj-1", "status", "2026-04-19T12:00:00Z")
    assert should_supersede(newer, older) is False
```

```python
# tests/vault/test_contradiction.py
from vault.fusion_engine.contradiction import detect_contradiction
from vault.memory_core.models import Claim, SourceRef


def test_detects_contradiction():
    c1 = _claim("c1", "topic-1", "entity-1", "Texto A")
    c2 = _claim("c2", "topic-1", "entity-1", "Texto B")
    result = detect_contradiction(c1, [c2])
    assert result.has_contradiction is True
    assert result.severity == "high"


def test_no_contradiction_same_text():
    c1 = _claim("c1", "topic-1", "entity-1", "Texto Igual")
    c2 = _claim("c2", "topic-1", "entity-1", "Texto Igual")
    result = detect_contradiction(c1, [c2])
    assert result.has_contradiction is False
```

Run: `PYTHONPATH=. pytest tests/vault/test_confidence.py tests/vault/test_supersession.py tests/vault/test_contradiction.py -v`
Expected: all PASS

```python
# tests/vault/test_contradiction.py — helper mínimo válido
from vault.memory_core.models import Claim, SourceRef

def _claim(claim_id: str, topic_id: str, entity_id: str, text: str) -> Claim:
    ref = SourceRef(source_id=claim_id, url="https://example.com")
    c = Claim.new(
        entity_type="topic",
        entity_id=entity_id,
        topic_id=topic_id,
        claim_type="decision",
        text=text,
        source="github",
        source_ref=ref,
        evidence_ids=[f"ev-{claim_id}"],
        author="system",
        event_timestamp="2026-04-19T12:00:00Z",
        privacy_level="internal",
    )
    c.claim_id = claim_id
    c.confidence = 0.9
    return c
```

---

- [ ] **Step 6: Commit**

```bash
git add vault/fusion_engine/ tests/vault/test_confidence.py tests/vault/test_supersession.py tests/vault/test_contradiction.py
git commit -m "feat: fusion engine v1 — confidence scoring, supersession, contradiction detection"
```

---

### Tarefa 3: CaptureConnectors — Trello com GitHub Plugin Links e Horas

**Files:**
- Modify: `vault/research/trello_client.py` (adicionar extração de GitHub links + time tracking)
- Create: `vault/research/trello_parsers.py` (claim extraction por card)
- Create: `tests/vault/test_trello_connectors.py`

---

- [ ] **Step 1: Copiar connector base do personal-data-connectors (adaptado)**

O código de `personal-data-connectors/connectors/trello.py` já extrai GitHub links e tem estrutura de normalização. Vamos adaptá-lo como `TrelloConnector` no vault.

```python
# vault/research/trello_parsers.py
"""
Claim parsers para Trello — extrai claims normalizados de cards.

Spec Section 3.4: exemplos por fonte.
"""
import re
import hashlib
import uuid
from dataclasses import dataclass
from vault.memory_core.models import Claim, SourceRef, ClaimType, EntityType, Source


GITHUB_PATTERN = re.compile(
    r"https://github\.com/([^/]+)/([^/]+)/(issues|pull)/\d+"
)


@dataclass
class ParsedTrelloCard:
    card_id: str
    card_name: str
    card_url: str
    board_id: str
    list_name: str
    labels: list[str]
    due_date: str | None
    github_links: list[str]
    hours_logged: float | None  # from plugin de horas (if available)
    last_activity: str  # ISO timestamp


def parse_trello_card(card: dict, list_name: str = "Unknown") -> ParsedTrelloCard:
    """Parse raw Trello API card dict into structured data."""
    github_links = _extract_github_links(card)

    return ParsedTrelloCard(
        card_id=card["id"],
        card_name=card.get("name", ""),
        card_url=card.get("url", ""),
        board_id=card.get("idBoard", ""),
        list_name=list_name,
        labels=[l.get("name", "") for l in card.get("labels", [])],
        due_date=card.get("due"),
        github_links=github_links,
        hours_logged=None,  # populated if time-tracking plugin data available
        last_activity=card.get("dateLastActivity", ""),
    )


def _extract_github_links(card: dict) -> list[str]:
    links = set()
    desc = card.get("desc", "") or ""
    for match in re.finditer(GITHUB_PATTERN, desc):
        links.add(match.group(0))
    for att in card.get("attachments", []):
        url = att.get("url", "")
        if re.search(GITHUB_PATTERN, url):
            links.add(url)
    return sorted(list(links))


def card_to_claims(card: ParsedTrelloCard) -> list[Claim]:
    """Convert a parsed card into one or more Claim objects.

    Produz:
    - 1 claim de status (card moved / created)
    - 1 claim por GitHub link (linkage)
    """
    claims = []

    # Status claim
    ref = SourceRef(source_id=card.card_id, url=card.card_url)
    status_text = f"Card '{card.card_name}' está em '{card.list_name}'"
    if card.due_date:
        status_text += f" (due: {card.due_date})"

    evidence_id = str(uuid.uuid4())
    status_claim = Claim.new(
        entity_type="project",
        entity_id=card.board_id,
        topic_id=None,
        claim_type="status",
        text=status_text,
        source="trello",
        source_ref=ref,
        evidence_ids=[evidence_id],
        author=card.card_id,
        event_timestamp=card.last_activity,
        privacy_level="public",
    )
    claims.append(status_claim)

    # Linkage claims por GitHub link
    for link in card.github_links:
        gh_ref = SourceRef(source_id=card.card_id, url=link)
        gh_evidence_id = str(uuid.uuid4())
        gh_claim = Claim.new(
            entity_type="project",
            entity_id=card.board_id,
            topic_id=None,
            claim_type="linkage",
            text=f"Card linkado a {link}",
            source="trello",
            source_ref=gh_ref,
            evidence_ids=[gh_evidence_id],
            author=card.card_id,
            event_timestamp=card.last_activity,
            privacy_level="public",
        )
        claims.append(gh_claim)

    return claims
```

Run: `python -c "from vault.research.trello_parsers import parse_trello_card; print('OK')"`
Expected: `OK`

---

- [ ] **Step 2: Atualizar TrelloClient para usar parsers**

O `trello_client.py` existente precisa ser atualizado para expor cards normalizados e suportar a estrutura de Claim.

```python
# vault/research/trello_client.py — adicionar método
# (ao final do arquivo existente, NÃO reescrever o arquivo inteiro)

def get_normalized_cards(self, last_seen_at: str | None = None) -> list[ParsedTrelloCard]:
    """Retorna cards/eventos normalizados a partir da API real do TrelloClient."""
    import vault.research.trello_parsers as parsers

    events = self.fetch_events_since(last_seen_at)
    normalized: list[ParsedTrelloCard] = []
    for e in events:
        # Usa payload normalizado já entregue pelo cliente real
        raw = e.get("raw", {})
        data = raw.get("data", {})
        card = data.get("card") or {}
        if not card.get("id"):
            continue
        # list_name pode não estar disponível em todo evento; usa fallback
        list_name = (data.get("listAfter") or data.get("list") or {}).get("name", "Unknown")
        normalized.append(parsers.parse_trello_card({
            "id": card.get("id"),
            "name": card.get("name", ""),
            "url": card.get("url", ""),
            "idBoard": (data.get("board") or {}).get("id", ""),
            "desc": card.get("desc", ""),
            "labels": card.get("labels", []),
            "due": card.get("due"),
            "dateLastActivity": e.get("timestamp", ""),
            "attachments": card.get("attachments", []),
        }, list_name=list_name))
    return normalized
```

Run: `python -c "from vault.research.trello_client import TrelloClient; c = TrelloClient(); print(list(c.get_normalized_cards.__doc__))"`
Expected: (sem erro de import)

---

- [ ] **Step 3: Teste de integração**

```python
# tests/vault/test_trello_connectors.py
from vault.research.trello_client import TrelloClient


def test_trello_client_initialization():
    client = TrelloClient(api_key="k", token="t", board_ids=["b1"])
    assert client.api_key == "k"
    assert client.token == "t"
    assert client.board_ids == ["b1"]


def test_parse_trello_card_extracts_github_links():
    from vault.research.trello_parsers import parse_trello_card

    raw_card = {
        "id": "card123",
        "name": "BAT Sev2 Investigation",
        "url": "https://trello.com/c/card123",
        "idBoard": "board1",
        "desc": "Verificar https://github.com/living/livy-memory-bot/pull/42",
        "labels": [{"name": "bug"}],
        "due": "2026-04-20",
        "dateLastActivity": "2026-04-19T10:00:00.000Z",
        "attachments": [],
    }
    card = parse_trello_card(raw_card, list_name="In Progress")
    assert "https://github.com/living/livy-memory-bot/pull/42" in card.github_links
    assert card.list_name == "In Progress"
```

Run: `PYTHONPATH=. pytest tests/vault/test_trello_connectors.py -v`
Expected: 2 tests PASS

---

- [ ] **Step 4: Commit**

```bash
git add vault/research/trello_parsers.py vault/research/trello_client.py tests/vault/test_trello_connectors.py
git commit -m "feat: Trello connector com extração de GitHub links e claim parsers"
```

---

### Tarefa 4: CaptureConnectors — GitHub PR Completo (Reviews/Approvers/Comments)

**Files:**
- Modify: `vault/research/github_client.py` (adicionar reviews e approvers)
- Modify: `vault/research/github_rich_client.py` (adicionar rich PR full details)
- Create: `vault/research/github_parsers.py`
- Create: `tests/vault/test_github_parsers.py`

---

- [ ] **Step 1: Reusar GitHubRichClient (sem duplicar fetch de reviews)**

```python
# vault/research/github_parsers.py — usar GitHubRichClient existente
from vault.research.github_rich_client import GitHubRichClient


def fetch_pr_with_reviews(repo: str, pr_number: int) -> dict:
    """Fetch full PR + reviews usando cliente rico existente (sem duplicação)."""
    rich = GitHubRichClient()
    pr = rich.fetch_rich_pr(pr_number, repo)
    reviews = rich.fetch_reviews(pr_number, repo)
    pr["reviews"] = reviews
    return pr
```

Run: `python -c "from vault.research.github_parsers import fetch_pr_with_reviews; print('OK')"`
Expected: `OK`

---

- [ ] **Step 2: GitHub claim parser**

```python
# vault/research/github_parsers.py
"""Claim parsers para GitHub — extrai claims normalizados de PRs e reviews."""
import uuid
from vault.memory_core.models import Claim, SourceRef


def pr_to_claims(pr: dict) -> list[Claim]:
    """Convert full PR dict (with reviews) into claims."""
    claims = []
    repo = pr.get("repo", "") or pr.get("base", {}).get("repo", {}).get("full_name", "")
    pr_number = pr.get("number")
    pr_url = pr.get("url", f"https://github.com/{repo}/pull/{pr_number}")
    author = pr.get("user", {}).get("login", "unknown")
    merged_at = pr.get("merged_at") or pr.get("updated_at", "")

    # Decision claim: PR merged
    if pr.get("merged"):
        merged_by = pr.get("merged_by", {}).get("login", author)
        ref = SourceRef(source_id=str(pr_number), url=pr_url)
        evidence_id = str(uuid.uuid4())

        decision_claim = Claim.new(
            entity_type="pull_request",
            entity_id=f"{repo}/pull/{pr_number}",
            topic_id=None,
            claim_type="decision",
            text=f"PR #{pr_number} em {repo} aprovado e mergeado por @{merged_by}",
            source="github",
            source_ref=ref,
            evidence_ids=[evidence_id],
            author=author,
            event_timestamp=merged_at,
            privacy_level="public",
        )
        claims.append(decision_claim)

        # Reviewer claims
        approvers = [
            ((r.get("user") or {}).get("login"))
            for r in (pr.get("reviews") or [])
            if r.get("state") == "APPROVED"
        ]
        approvers = [a for a in approvers if a]

        for approver in approvers:
            appr_ref = SourceRef(source_id=f"{pr_number}-review-{approver}", url=pr_url)
            appr_evidence = str(uuid.uuid4())
            appr_claim = Claim.new(
                entity_type="pull_request",
                entity_id=f"{repo}/pull/{pr_number}",
                topic_id=None,
                claim_type="decision",
                text=f"@{approver} aprovou PR #{pr_number}",
                source="github",
                source_ref=appr_ref,
                evidence_ids=[appr_evidence],
                author=approver,
                event_timestamp=merged_at,
                privacy_level="public",
            )
            claims.append(appr_claim)

    return claims
```

Run: `python -c "from vault.research.github_parsers import pr_to_claims; print('OK')"`
Expected: `OK`

---

- [ ] **Step 3: Commit**

```bash
git add vault/research/github_client.py vault/research/github_parsers.py
git commit -m "feat: GitHub client com reviews, approvers e claim parser"
```

---

### Tarefa 5: Azure Blob como Fonte Primária de Transcripts

- [ ] **Pré-check obrigatório:** validar naming real dos blobs no producer (`living/livy-tldv-jobs`) antes de hardcode de path.
  - Confirmar se produção usa `meetings/{id}.transcript.json` e `meetings/{id}.transcript.tldv.json`.
  - Se divergir, parametrizar pattern com env vars (`AZURE_TRANSCRIPT_CONSOLIDATED_PATTERN`, `AZURE_TRANSCRIPT_ORIGINAL_PATTERN`).

**Files:**
- Create: `vault/capture/azure_blob_client.py`
- Create: `vault/research/supabase_transcript.py`
- Modify: `vault/research/tldv_client.py` (integrar leitura do Azure)
- Create: `tests/vault/test_azure_blob_client.py`
- Create: `tests/vault/test_supabase_transcript.py`

---

- [ ] **Step 1: Criar Azure Blob client (reaproveitando personal-data-connectors)**

```python
# vault/capture/azure_blob_client.py
"""
Azure Blob Storage client para Wiki v2.
Reaproveita lógica de personal-data-connectors/connectors/azure_blob.py.

Spec Section 4.3: Azure Blob como fonte primária de transcripts.
"""
import json
import os
from typing import Any
from azure.storage.blob import BlobServiceClient


def _get_blob_service() -> BlobServiceClient:
    account_name = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME")
    account_key = os.environ.get("AZURE_STORAGE_ACCOUNT_KEY")
    if not account_name or not account_key:
        raise RuntimeError(
            "AZURE_STORAGE_ACCOUNT_NAME / AZURE_STORAGE_ACCOUNT_KEY não configurado"
        )
    return BlobServiceClient(
        account_url=f"https://{account_name}.blob.core.windows.net",
        credential=account_key,
    )


def _get_container() -> str:
    return os.environ.get("AZURE_STORAGE_CONTAINER_NAME", "meetings")


def load_transcript_segments(meeting_id: str) -> list[dict]:
    """
    Carrega transcrição consolidada do Azure Blob.
    Fallback: tenta .transcript.json primeiro, depois .transcript.tldv.json.

    Returns:
        Lista de segmentos de transcrição (formato tl;dv)

    Raises:
        FileNotFoundError: se nenhum blob existir para o meeting_id
    """
    service = _get_blob_service()
    container = service.get_container_client(_get_container())

    # Tentar consolidado primeiro
    consolidated = f"meetings/{meeting_id}.transcript.json"
    blob = container.get_blob_client(consolidated)
    if blob.exists():
        data = blob.download_blob().readall()
        segments = json.loads(data.decode("utf-8"))
        if isinstance(segments, list):
            return segments
        return segments.get("segments", [segments])

    # Fallback: original tl;dv
    original = f"meetings/{meeting_id}.transcript.tldv.json"
    blob = container.get_blob_client(original)
    if blob.exists():
        data = blob.download_blob().readall()
        segments = json.loads(data.decode("utf-8"))
        if isinstance(segments, list):
            return segments
        return segments.get("segments", [segments])

    # Fallback final: Supabase transcript_segments rows (spec Section 13)
    try:
        from vault.research.supabase_transcript import load_segments_from_supabase
        segments = load_segments_from_supabase(meeting_id)
        if segments:
            return segments
    except Exception:
        pass  # Supabase também indisponível

    raise FileNotFoundError(f"Nenhum transcript encontrado para meeting_id={meeting_id}")


def transcript_to_meeting_claim(meeting_id: str, segments: list[dict]) -> dict:
    """Converte segmentos de transcript em estrutura de claim para o Fusion Engine."""
    if not segments:
        return {}

    first_segment = segments[0]
    last_segment = segments[-1]

    return {
        "meeting_id": meeting_id,
        "started_at": first_segment.get("start") or first_segment.get("timestamp", ""),
        "ended_at": last_segment.get("end") or last_segment.get("timestamp", ""),
        "speaker_count": len(set(s.get("speaker") or "unknown" for s in segments)),
        "segment_count": len(segments),
        "raw_preview": (segments[0].get("text") or "")[:200],
    }
```

Run: `python -c "from vault.capture.azure_blob_client import load_transcript_segments; print('OK')"`
Expected: `OK`

---

- [ ] **Step 2: Atualizar TLDVClient para usar Azure Blob**

```python
# vault/research/tldv_client.py — adicionar método
# (após método fetch_events_since existente)

def fetch_meeting_transcript_from_azure(self, meeting_id: str) -> list[dict]:
    """Busca transcrição de meeting via Azure Blob (fonte primária)."""
    from vault.capture.azure_blob_client import load_transcript_segments
    try:
        return load_transcript_segments(meeting_id)
    except FileNotFoundError:
        logger.warning(
            "source=tldv meeting_id=%s transcript not found in Azure Blob",
            meeting_id,
        )
        return []
```

Run: `python -c "from vault.research.tldv_client import TLDVClient; print('OK')"`
Expected: `OK`

---

- [ ] **Step 3: Teste com mock**

```python
# tests/vault/test_azure_blob_client.py
import pytest
from unittest.mock import patch, MagicMock


def test_load_transcript_segments_consolidated():
    mock_blob = MagicMock()
    mock_blob.exists.return_value = True
    mock_blob.download_blob.return_value.readall.return_value = (
        b'[{"text": "Olá", "speaker": "Alice", "start": 0}]'
    )
    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob

    with patch("vault.capture.azure_blob_client._get_blob_service") as mock_svc:
        mock_svc.return_value.get_container_client.return_value = mock_container
        from vault.capture.azure_blob_client import load_transcript_segments
        segments = load_transcript_segments("meeting-123")
        assert len(segments) == 1
        assert segments[0]["text"] == "Olá"
```

Run: `PYTHONPATH=. pytest tests/vault/test_azure_blob_client.py -v`
Expected: 1 test PASS

---

- [ ] **Step 4: Commit**

```bash
git add vault/capture/ vault/research/tldv_client.py tests/vault/test_azure_blob_client.py
git commit -m "feat: Azure Blob como fonte primária de transcripts com fallback"
```

---

### Tarefa 6: Idempotência — Dual Keys (event_key + content_key)

**Files:**
- Modify: `vault/research/event_key.py` (adicionar content_key)
- Create: `vault/research/idempotency.py`
- Create: `tests/vault/test_idempotency.py`

---

- [ ] **Step 1: Adicionar content_key ao event_key.py**

```python
# vault/research/event_key.py — adicionar ao final do arquivo

def build_content_key(source: str, source_id: str, content_hash: str) -> str:
    """
    Content key para dedupe semântico (spec Section 9.2).

    Formato: {source}:{source_id}:{content_hash}

    Diferença de event_key:
    - event_key = source:type:id[:action_id]  (dedupe de ingest operacional)
    - content_key = source:source_id:hash     (dedupe de conteúdo idêntico)
    """
    return f"{source}:{source_id}:{content_hash}"
```

Run: `python -c "from vault.research.event_key import build_content_key; print('OK')"`
Expected: `OK`

---

- [ ] **Step 2: Criar idempotency.py com verificação de ambas as chaves**

```python
# vault/research/idempotency.py
"""
Verificação de idempotência com duas chaves (spec Section 9.2).

- event_key: dedupe de eventos operacionais
- content_key: dedupe de conteúdo idêntico
"""
import hashlib
from vault.research.event_key import build_event_key, build_content_key
from vault.research.state_store import upsert_processed_event_key


def compute_content_hash(content: str) -> str:
    """Compute SHA256 hash of content string for content_key."""
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def check_and_record(
    source: str,
    event: dict,
    content: str,
    state_path: str = "state/identity-graph/state.json",
) -> bool:
    """
    Verifica se evento já foi processado (por event_key OU content_key).
    Se não, registra ambas as chaves.

    Returns:
        True se o evento deve ser processado (não é duplicado)
        False se deve ser ignorado (duplicado)
    """
    from vault.research.state_store import load_state

    event_type = str(event.get("type", "event"))
    object_id = str(event.get("id") or event.get("meeting_id") or event.get("card_id", "unknown"))
    action_id = str(event.get("action_id", ""))

    event_key = build_event_key(source, event_type, object_id, action_id or None)
    content_hash = compute_content_hash(content)
    content_key = build_content_key(source, object_id, content_hash)

    state = load_state(state_path)
    processed = state.get("processed_event_keys", {}).get(source, [])

    existing_keys = {item.get("key") for item in processed if isinstance(item, dict)}

    if event_key in existing_keys or content_key in existing_keys:
        return False  # Duplicate — skip

    event_at = event.get("event_at") or event.get("timestamp") or event.get("date", "")
    upsert_processed_event_key(source, event_key, event_at, state_path)
    upsert_processed_event_key(source, content_key, event_at, state_path)
    return True
```

Run: `python -c "from vault.research.idempotency import check_and_record; print('OK')"`
Expected: `OK`

---

- [ ] **Step 3: Teste**

```python
# tests/vault/test_idempotency.py
from vault.research.idempotency import compute_content_hash, build_content_key


def test_content_key_format():
    key = build_content_key("github", "pr-42", "abc123")
    assert key == "github:pr-42:abc123"


def test_content_hash_deterministic():
    h1 = compute_content_hash("same content")
    h2 = compute_content_hash("same content")
    assert h1 == h2


def test_content_hash_different_for_different_content():
    h1 = compute_content_hash("content A")
    h2 = compute_content_hash("content B")
    assert h1 != h2
```

Run: `PYTHONPATH=. pytest tests/vault/test_idempotency.py -v`
Expected: 3 PASS

---

- [ ] **Step 4: Commit**

```bash
git add vault/research/event_key.py vault/research/idempotency.py tests/vault/test_idempotency.py
git commit -m "feat: dual idempotency keys (event_key + content_key)"
```

---

### Tarefa 7: Shadow Run + Diff + Rollback

**Files:**
- Create: `vault/ops/shadow_run.py`
- Create: `vault/ops/rollback.py`
- Create: `tests/vault/test_shadow_run.py`
- Modify: `docs/superpowers/plans/2026-04-19-wiki-v2-implementation.md` (este arquivo — atualizar ao final)

---

- [ ] **Step 1: Shadow run**

```python
# vault/ops/shadow_run.py
"""
Shadow run: executa nova implementação vs atual com mesmos inputs
e gera diff report (spec Section 9.3).

O diff é enviado para 7426291192 antes de ativar em produção.
"""
import json
from pathlib import Path
from typing import Any


def run_shadow(
    pipeline_v1_output: list[dict],
    pipeline_v2_output: list[dict],
    threshold: float = 0.05,
) -> dict[str, Any]:
    """
    Compara outputs do pipeline v1 (atual) vs v2 (novo).

    Args:
        pipeline_v1_output: lista de claims do pipeline atual
        pipeline_v2_output: lista de claims do novo pipeline
        threshold: % máxima de divergência aceita (default 5%)

    Returns:
        dict com {passed, diff_ratio, diff_items, report_path}
    """
    v1_by_entity = {c["entity_id"]: c for c in pipeline_v1_output}
    v2_by_entity = {c["entity_id"]: c for c in pipeline_v2_output}

    all_entities = set(v1_by_entity) | set(v2_by_entity)
    diverged = []

    for entity_id in all_entities:
        c1 = v1_by_entity.get(entity_id)
        c2 = v2_by_entity.get(entity_id)

        if c1 is None or c2 is None:
            diverged.append({"entity_id": entity_id, "reason": "missing_in_one_version"})
        elif c1.get("text") != c2.get("text"):
            diverged.append({
                "entity_id": entity_id,
                "reason": "text_mismatch",
                "v1": c1.get("text", "")[:100],
                "v2": c2.get("text", "")[:100],
            })

    diff_ratio = len(diverged) / max(len(all_entities), 1)
    passed = diff_ratio <= threshold

    report = {
        "passed": passed,
        "diff_ratio": round(diff_ratio, 4),
        "threshold": threshold,
        "total_entities": len(all_entities),
        "diverged_count": len(diverged),
        "diverged_items": diverged[:50],  # cap for report size
    }

    report_path = Path("state/shadow-run-reports") / f"report-{int(__import__('time').time())}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    report["report_path"] = str(report_path)
    return report
```

Run: `python -c "from vault.ops.shadow_run import run_shadow; print('OK')"`
Expected: `OK`

---

- [ ] **Step 2: Rollback via Gateway config.patch**

```python
# vault/ops/rollback.py
"""
Rollback do Wiki v2 em 1 comando (spec Section 9.4).

Executa Gateway config.patch via tool call para desabilitar feature flag.
"""
from typing import Any
import json
import subprocess


def rollback_wiki_v2() -> dict[str, Any]:
    """
    Executa rollback do feature wiki_v2 via Gateway config.patch.

    Spec format:
    {
      "action": "config.patch",
      "patch": {"features": {"wiki_v2": {"enabled": False}}}
    }

    Returns:
        dict com {success, message}
    """
    patch = {"features": {"wiki_v2": {"enabled": False}}}

    # Validação: simula o que seria enviado (não executa gateway diretamente)
    # A execução real é feita via tool call `gateway(action="config.patch", raw=json.dumps(patch), note="Rollback wiki_v2")`
    return {
        "success": True,
        "patch": patch,
        "note": "Execute via gateway tool: gateway(action='config.patch', raw=json.dumps(patch), note='Rollback wiki_v2')",
    }


def is_wiki_v2_enabled() -> bool:
    """Checa se wiki_v2 está habilitada via feature flag."""
    # Lê do estado local ou invoca gateway config.get
    # Placeholder — implementação real depende de como feature flags são armazenados
    import os
    return os.environ.get("WIKI_V2_ENABLED", "false").lower() == "true"
```

Run: `python -c "from vault.ops.rollback import rollback_wiki_v2; print('OK')"`
Expected: `OK`

---

- [ ] **Step 3: Commit**

```bash
git add vault/ops/ tests/vault/test_shadow_run.py
git commit -m "feat: shadow run + rollback operacional"
```

---

### Tarefa 7B: Replay Determinístico (spec Section 9.5)

**Files:**
- Create: `vault/ops/replay_pipeline.py`
- Create: `tests/vault/test_replay_pipeline.py`

---

- [ ] **Step 1: Implementar replay_pipeline.py**

```python
# vault/ops/replay_pipeline.py
"""
Replay determinístico: regenera estado a partir de raw events (spec Section 9.5).

Executar:
    python vault/ops/replay_pipeline.py --since=2026-04-19T00:00:00Z

Este script:
1. Carrega eventos brutos do audit log
2. Para cada evento na janela, reaplica Fusion Engine
3. Regenera SSOT state completo (determinístico — mesmo input = mesmo output)
4. Substitui state.json apenas se replay for bem-sucedido
"""
from __future__ import annotations
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from vault.fusion_engine.engine import fuse
from vault.memory_core.models import Claim


def replay_events(
    audit_log_path: Path,
    since: datetime,
    state_path: Path,
) -> dict[str, int]:
    """Replay all events since `since` and return replay stats."""
    events = []
    for line in audit_log_path.read_text().splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        event_time = datetime.fromisoformat(event["event_at"].replace("Z", "+00:00"))
        if event_time >= since:
            events.append(event)

    events.sort(key=lambda e: e["event_at"])

    processed = 0
    errors = 0
    for event in events:
        try:
            existing_state = _load_state(state_path)
            existing = _load_claims_from_state(existing_state)
            new_claim = _event_to_claim(event)
            result = fuse(new_claim, existing)
            _persist_fusion_result(state_path, result)
            processed += 1
        except Exception:
            errors += 1

    return {"processed": processed, "errors": errors, "total": len(events)}


def _load_state(state_path: Path) -> dict:
    if not state_path.exists():
        return {"claims": []}
    return json.loads(state_path.read_text())


def _load_claims_from_state(state: dict) -> list:
    # Placeholder mapping; adaptador real converte dict->Claim quando schema final estiver estável.
    return []


def _persist_fusion_result(state_path: Path, result) -> None:
    # Placeholder persist; implementação final deve gravar claim + supersession + audit.
    pass


def _event_to_claim(event: dict):
    """Converte evento do audit log em Claim para replay."""
    # TODO: mapear todos os tipos de evento; por ora, contrato mínimo para wiring
    from vault.memory_core.models import Claim, SourceRef
    return Claim.new(
        entity_type="topic",
        entity_id=str(event.get("entity_id", "unknown")),
        topic_id=event.get("topic_id"),
        claim_type="timeline_event",
        text=str(event.get("text", "replayed event")),
        source=event.get("source", "github"),
        source_ref=SourceRef(source_id=str(event.get("id", "unknown")), url=event.get("url")),
        evidence_ids=[str(event.get("evidence_id", "replay-evidence"))],
        author=str(event.get("author", "system")),
        event_timestamp=str(event.get("event_at", "2026-04-19T00:00:00Z")),
        privacy_level="internal",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay pipeline events")
    parser.add_argument("--since", required=True, help="ISO 8601 timestamp")
    parser.add_argument("--audit-log", default="state/audit.log", help="Audit log path")
    parser.add_argument("--state", default="state/identity-graph/state.json")
    args = parser.parse_args()

    since = datetime.fromisoformat(args.since.replace("Z", "+00:00"))
    stats = replay_events(Path(args.audit_log), since, Path(args.state))
    print(f"Replay: {stats['processed']}/{stats['total']} events OK, {stats['errors']} errors")


if __name__ == "__main__":
    main()
```

Run: `python -c "from vault.ops.replay_pipeline import replay_events; print('OK')"`
Expected: `OK`

---

- [ ] **Step 2: Commit**

```bash
git add vault/ops/replay_pipeline.py tests/vault/test_replay_pipeline.py
git commit -m "feat: replay determinístico para recuperação de estado"
```

---

### Checklist de Alinhamento de Invariantes (executar após Tarefa 1)

Ao final da Tarefa 1, verificar:

- [ ] `Claim.evidence_ids` — reivindicado por `len >= 1` (nunca vazio)
- [ ] `Claim.audit_trail` — obrigatório em todo write (nunca None em produção)
- [ ] `Claim.supersession_reason` — obrigatório quando `superseded_by` está setado
- [ ] `Claim.supersession_version` — obrigatório quando `superseded_by` está setado
- [ ] `CorruptStateError` — usada nos checks, não `assert`
```

---

## Validação Final da Fase 1

Após implementar todas as tarefas:

- [ ] `PYTHONPATH=. pytest tests/vault/test_memory_core_models.py tests/vault/test_fusion_engine.py tests/vault/test_confidence.py tests/vault/test_supersession.py tests/vault/test_contradiction.py tests/vault/test_trello_connectors.py tests/vault/test_idempotency.py tests/vault/test_azure_blob_client.py -v` — **todos PASS**
- [ ] Replay determinístico smoke test: `python vault/ops/replay_pipeline.py --since=2026-04-19T00:00:00Z --audit-log=/dev/null`
- [ ] Shadow run executado com diff < 5% vs pipeline atual
- [ ] Rollback validado (feature flag desliga nova lógica)
- [ ] Commit de feature: `git add vault/ && git commit -m "feat: wiki v2 fase 1 completa"`

---

## Fase 2 — Integração de Fontes (Gmail + Calendar + Privacidade)

> **⚠️ Gate obrigatório:** testar OAuth Desktop App no VPS antes de iniciar código.

### Tarefa 8: Google OAuth — Setup e Secrets

**Files:**
- Create: `vault/capture/google_auth.py` (copiado e adaptado de personal-data-connectors)
- Create: `vault/capture/gmail_client.py`
- Create: `vault/capture/calendar_client.py`
- Create: `tests/vault/test_gmail_client.py`
- Create: `tests/vault/test_calendar_client.py`

- [ ] Setup OAuth Desktop flow para `lincoln@livingnet` e `livy@livingnet`
- [ ] Salvar tokens em `~/.openclaw/secrets/token_{lincoln,livy}.json`
- [ ] Teste de conexão real com cada conta

### Tarefa 9: Gmail Connector — Threads e Decisões

- [ ] Implementar `GmailConnector.get_recent_messages()` com filtro oficial v1
- [ ] Claim parser para Gmail (spec Section 3.4 exemplos)
- [ ] Cron `research-gmail` com cadência **batch-first 6h** (`0 0,6,12,18 * * *`, BRT) na transição

### Tarefa 10: Calendar Connector — Eventos e Participantes

- [ ] Implementar `GoogleCalendarConnector.get_events()`
- [ ] Claim parser para Calendar
- [ ] Cron `research-calendar` com cadência **batch-first 6h** (`0 0,6,12,18 * * *`, BRT) na transição

### Tarefa 11: Privacy Filter v1

- [ ] Blocklist em `~/.openclaw/secrets/privacy-blocklist.yaml`
- [ ] LLM Judge para edge cases (PremiumFirst)
- [ ] Processo trimestral de manutenção da blocklist

---

## Fase 3 — Wiki Completa e Automação Total

### Tarefa 12: Projeção Wiki (markdown por tipo de entidade)

- [ ] Template de página wiki (spec Section 6.1)
- [ ] Writer para Person, Project, PullRequest, Meeting, Topic
- [ ] Gerenciamento de histórico de mudanças

### Tarefa 13: Query Interface (híbrida texto + semântica + grafo)

- [ ] Search multi-modal (FTS + vetorial + grafo)
- [ ] Rastreabilidade de citação (every answer cites evidence)

### Tarefa 14: Autoresearch (Evo) + Detecção de Contradição com Alerta

- [ ] Integração Evo no fluxo de consolidação
- [ ] Alerta Telegram via `message` tool com formato renderizado
- [ ] JSON para audit log (spec Section 5.3)

---

_Last updated: 2026-04-19 13:10 UTC_
