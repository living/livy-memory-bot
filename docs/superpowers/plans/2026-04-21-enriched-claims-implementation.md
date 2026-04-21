# Enriched Claims (Decision + Linkage) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aumentar a qualidade semântica do vault, elevando claims `decision` + `linkage` (>= 40% combinado) com deduplicação semântica, triagem (`needs_review`) e guardrails operacionais.

**Architecture:** Implementar em 3 ondas: (A) extração enriquecida por fonte (TLDV/GitHub/Trello), (B) fusão+confiança+dedupe semântico no SSOT, (C) observabilidade com KPIs e alertas. A implementação preserva o `content_key` existente e adiciona chaves complementares (`decision_key`, `linkage_key`) para reduzir ruído sem quebrar compatibilidade.

**Tech Stack:** Python 3.12, pytest, módulo research (`vault/research/*`), fusion engine (`vault/fusion_engine/*`), memory core (`vault/memory_core/models.py`), cron research-consolidation.

---

## Scope/Dependency Notes

- Este plano implementa a spec `docs/superpowers/specs/2026-04-21-enriched-claims-design.md` (v1.2).
- O item mais sensível é Trello: novos endpoints por card são pré-requisito para decisão por comentário/checklist.
- Ordem obrigatória: Tasks 1-2 antes de Tasks 3-5; Task 6 depende de 3-5; Task 7 depende de 6.

---

## File Map (antes de executar)

### Criar
- `tests/vault/test_claim_model.py` — cobertura de novos campos `needs_review`, `review_reason`.
- `tests/vault/ops/test_quality_guardrails.py` — valida guardrails de KPIs por 2 ciclos.

### Modificar
- `vault/memory_core/models.py` — adicionar campos opcionais `needs_review`, `review_reason`.
- `vault/research/trello_client.py` — adicionar `get_card_comments(card_id)` e `get_card_checklists(card_id)`.
- `vault/research/trello_parsers.py` — gerar `decision` por comentário/checklist com fallback.
- `vault/research/github_parsers.py` — linkage completo (`from/to_entity`) + decisão por linguagem normativa restritiva.
- `vault/research/tldv_client.py` — geração de `decision` de `summaries.decisions` + fallback regex.
- `vault/fusion_engine/confidence.py` — bônus por `evidence_ids` + convergência via `other_sources`.
- `vault/fusion_engine/supersession.py` — proteger decision de sobrescrita por status + similaridade textual.
- `vault/research/state_store.py` — manter `content_key` e adicionar `decision_key`/`linkage_key` complementares.
- `vault/crons/research_consolidation_cron.py` — KPIs/thresholds/alertas.
- `HEARTBEAT.md` — seção "Qualidade de Claims".

### Testes existentes para expandir
- `tests/research/test_trello_parsers.py`
- `tests/research/test_github_parsers.py`
- `tests/research/test_tldv_client.py`
- `tests/vault/fusion_engine/test_confidence.py`
- `tests/vault/fusion_engine/test_supersession.py`
- `tests/vault/research/test_state_store.py`

---

### Task 1: Claim model extension (`needs_review`)

**Files:**
- Modify: `vault/memory_core/models.py`
- Create: `tests/vault/test_claim_model.py`

- [ ] **Step 1: Write failing tests for new fields**

```python
# tests/vault/test_claim_model.py
from vault.memory_core.models import Claim


def test_claim_defaults_needs_review_false():
    c = Claim(...)
    assert c.needs_review is False
    assert c.review_reason is None


def test_claim_accepts_needs_review_and_reason():
    c = Claim(..., needs_review=True, review_reason="sem_evidencia")
    assert c.needs_review is True
    assert c.review_reason == "sem_evidencia"
```

- [ ] **Step 2: Run test and confirm fail**

Run: `PYTHONPATH=. pytest tests/vault/test_claim_model.py -q`
Expected: FAIL (fields inexistentes).

- [ ] **Step 3: Implement fields in model (minimal change)**

```python
# vault/memory_core/models.py (dataclass Claim)
needs_review: bool = False
review_reason: str | None = None
```

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/vault/test_claim_model.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add vault/memory_core/models.py tests/vault/test_claim_model.py
git commit -m "feat(memory-core): add needs_review and review_reason to Claim"
```

---

### Task 2: Trello client card-level data (comments/checklists)

**Files:**
- Modify: `vault/research/trello_client.py`
- Test: `tests/research/test_trello_client.py` (create if missing)

- [ ] **Step 1: Write failing tests for card comments/checklists endpoints**

```python
def test_get_card_comments_calls_commentCard_endpoint(...):
    ...

def test_get_card_checklists_calls_card_checklists_endpoint(...):
    ...
```

- [ ] **Step 2: Run targeted tests**

Run: `PYTHONPATH=. pytest tests/research/test_trello_client.py -q`
Expected: FAIL.

- [ ] **Step 3: Implement methods**

```python
def get_card_comments(self, card_id: str) -> list[dict]:
    # /cards/{id}/actions?filter=commentCard

def get_card_checklists(self, card_id: str) -> list[dict]:
    # /cards/{id}/checklists
```

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/research/test_trello_client.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add vault/research/trello_client.py tests/research/test_trello_client.py
git commit -m "feat(research): add Trello card comments/checklists client methods"
```

---

### Task 3: Trello parser enrichment (decision + fallback)

**Files:**
- Modify: `vault/research/trello_parsers.py`
- Modify/Test: `tests/research/test_trello_parsers.py`

- [ ] **Step 1: Add failing tests for decision extraction from comments/checklists**

```python
def test_card_comment_with_decision_language_generates_decision_claim():
    ...

def test_missing_actions_logs_warning_and_skips_decision_claims():
    ...
```

- [ ] **Step 2: Run tests (should fail)**

Run: `PYTHONPATH=. pytest tests/research/test_trello_parsers.py -q`

- [ ] **Step 3: Implement parser additions**

- Regex decisório com contexto >=5 palavras.
- `needs_review=True`, `review_reason="comentario_trello"`, `confidence=0.40`.
- Warning `trello_comments_unavailable` quando dados não vierem.

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/research/test_trello_parsers.py -q`

- [ ] **Step 5: Commit**

```bash
git add vault/research/trello_parsers.py tests/research/test_trello_parsers.py
git commit -m "feat(research): enrich Trello claims with decision extraction and fallback"
```

---

### Task 4: GitHub parser enrichment (linkage contract + normative decisions)

**Files:**
- Modify: `vault/research/github_parsers.py`
- Modify/Test: `tests/research/test_github_parsers.py`

- [ ] **Step 1: Add failing tests for linkage fields (`from_entity`, `to_entity`, `relation`)**

```python
def test_github_refs_generate_linkage_with_from_to_entity():
    ...

def test_conventional_commit_title_does_not_auto_generate_decision():
    ...

def test_normative_language_generates_decision_needs_review():
    ...
```

- [ ] **Step 2: Run tests (fail expected)**

Run: `PYTHONPATH=. pytest tests/research/test_github_parsers.py -q`

- [ ] **Step 3: Implement minimal parser changes**

- Relações: `implements|blocks|mentions`.
- Evitar regex que captura conventional commits genéricos.
- `decision` com `needs_review` quando linguagem normativa detectada.
- Exceção obrigatória da spec: se PR tiver label forte (`architecture` ou `breaking-change`), não marcar automaticamente `needs_review` por esse motivo.

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/research/test_github_parsers.py -q`

- [ ] **Step 5: Commit**

```bash
git add vault/research/github_parsers.py tests/research/test_github_parsers.py
git commit -m "feat(research): enrich GitHub claims with canonical linkage and normative decisions"
```

---

### Task 5: TLDV enrichment (`summaries.decisions` + regex fallback)

**Files:**
- Modify: `vault/research/tldv_client.py`
- Modify/Test: `tests/research/test_tldv_client.py`

- [ ] **Step 1: Add failing tests**

```python
def test_summaries_decisions_generate_decision_claims():
    ...

def test_topics_regex_fallback_generates_low_confidence_decision():
    ...
```

- [ ] **Step 2: Run tests (fail expected)**

Run: `PYTHONPATH=. pytest tests/research/test_tldv_client.py -q`

- [ ] **Step 3: Implement extraction rules**

- Structured `decisions` -> `decision` com confiança alta.
- Regex fallback -> `confidence=0.45`, `needs_review=True`, `review_reason="regex_fallback"`.
- Linkage cruzado de meeting para PR/card/reunião quando houver referências, com relações explícitas:
  - PR -> `discusses`
  - Card Trello -> `mentions`
  - Reunião relacionada -> `relates_to`.

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/research/test_tldv_client.py -q`

- [ ] **Step 5: Commit**

```bash
git add vault/research/tldv_client.py tests/research/test_tldv_client.py
git commit -m "feat(research): add TLDV decision extraction and fallback linkage"
```

---

### Task 6: Confidence + convergence wiring

**Files:**
- Modify: `vault/fusion_engine/confidence.py`
- Modify/Test: `tests/vault/fusion_engine/test_confidence.py`

- [ ] **Step 1: Add failing tests for evidence bonus and convergence behavior**

```python
def test_decision_with_evidence_ids_gets_bonus():
    ...

def test_linkage_multisource_convergence_uses_other_sources_bonus():
    ...
```

- [ ] **Step 2: Run tests (fail expected)**

Run: `PYTHONPATH=. pytest tests/vault/fusion_engine/test_confidence.py -q`

- [ ] **Step 3: Implement minimal adjustments**

- Bonus `+0.15` para `decision` com `evidence_ids`.
- Penalidade obrigatória da spec: `-0.10` para claims extraídas por regex de linguagem.
- Reuso de `other_sources` (sem duplicar mecanismo paralelo).
- `needs_review`/`review_reason` canônicos quando sem evidência ou baixa confiança:
  - `sem_evidencia`
  - `baixa_confianca`
  - `regex_fallback`
  - `comentario_trello`.

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/vault/fusion_engine/test_confidence.py -q`

- [ ] **Step 5: Commit**

```bash
git add vault/fusion_engine/confidence.py tests/vault/fusion_engine/test_confidence.py
git commit -m "feat(fusion): add evidence_ids bonus and calibrated needs_review logic"
```

---

### Task 7: Supersession hardening for decisions

**Files:**
- Modify: `vault/fusion_engine/supersession.py`
- Modify/Test: `tests/vault/fusion_engine/test_supersession.py`

- [ ] **Step 1: Add failing tests**

```python
def test_status_never_supersedes_decision():
    ...

def test_decision_supersedes_only_with_similarity_or_explicit_reason():
    ...
```

- [ ] **Step 2: Run tests (fail expected)**

Run: `PYTHONPATH=. pytest tests/vault/fusion_engine/test_supersession.py -q`

- [ ] **Step 3: Implement guarded supersession**

- Similaridade textual `SequenceMatcher > 0.7` para decision->decision.
- Bloqueio explícito de status->decision.

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/vault/fusion_engine/test_supersession.py -q`

- [ ] **Step 5: Commit**

```bash
git add vault/fusion_engine/supersession.py tests/vault/fusion_engine/test_supersession.py
git commit -m "feat(fusion): protect decisions in supersession and add similarity gate"
```

---

### Task 8: State store semantic dedupe keys (complementary to content_key)

**Files:**
- Modify: `vault/research/state_store.py`
- Modify/Test: `tests/vault/research/test_state_store.py`

- [ ] **Step 1: Add failing tests**

```python
def test_content_key_still_primary_dedupe():
    ...

def test_decision_key_prevents_duplicate_decision_when_content_differs():
    ...

def test_linkage_key_prevents_duplicate_linkage():
    ...
```

- [ ] **Step 2: Run tests (fail expected)**

Run: `PYTHONPATH=. pytest tests/vault/research/test_state_store.py -q`

- [ ] **Step 3: Implement keys as secondary indexes**

- Preserve `content_key` as first gate.
- Add `decision_key` and `linkage_key` gates only if `content_key` absent.
- Regra obrigatória da spec: `decision_key` só deduplica quando claim existente tiver `confidence >= 0.7`.
- `linkage_key` pode deduplicar independentemente do confidence (chave relacional exata).
- No supersession side effects here.

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/vault/research/test_state_store.py -q`

- [ ] **Step 5: Commit**

```bash
git add vault/research/state_store.py tests/vault/research/test_state_store.py
git commit -m "feat(research): add semantic dedupe keys complementary to content_key"
```

---

### Task 9: Quality guardrails cron + tests

**Files:**
- Modify: `vault/crons/research_consolidation_cron.py`
- Create: `tests/vault/ops/test_quality_guardrails.py`

- [ ] **Step 1: Add failing tests for KPI thresholds and 2-cycle alert trigger**

```python
def test_quality_guardrail_alert_triggers_after_two_consecutive_bad_cycles():
    ...
```

- [ ] **Step 2: Run tests (fail expected)**

Run: `PYTHONPATH=. pytest tests/vault/ops/test_quality_guardrails.py -q`

- [ ] **Step 3: Implement metrics/threshold logic**

- `%decision`, `%linkage`, `%status`, `%needs_review`, `%with_evidence`.
- Emit `WARN: quality_guardrail_fail` with payload.

- [ ] **Step 4: Re-run tests**

Run: `PYTHONPATH=. pytest tests/vault/ops/test_quality_guardrails.py -q`

- [ ] **Step 5: Commit**

```bash
git add vault/crons/research_consolidation_cron.py tests/vault/ops/test_quality_guardrails.py
git commit -m "feat(cron): add enriched-claims quality guardrails and alerting"
```

---

### Task 10: Documentation + heartbeat + full verification

**Files:**
- Modify: `HEARTBEAT.md`
- Modify: `memory/curated/livy-memory-agent.md` (registrar rollout, se necessário)

- [ ] **Step 1: Update HEARTBEAT quality section**

Adicionar tabela de métricas e limiares no formato da spec.

- [ ] **Step 2: Run canonical test suites**

Run:
- `PYTHONPATH=. pytest tests/research/ -q`
- `PYTHONPATH=. pytest tests/vault/ -q`

Expected: PASS full suites.

- [ ] **Step 3: Smoke run**

Run one controlled execution:
- `python3 vault/crons/research_github_cron.py`
- `python3 vault/crons/research_tldv_cron.py`
- `python3 vault/crons/research_trello_cron.py`
- `python3 vault/crons/research_consolidation_cron.py`

Check:
- claims tipo decision/linkage aparecem;
- guardrails calculam percentuais;
- sem regressão crítica no audit.

- [ ] **Step 4: Final commit**

```bash
git add HEARTBEAT.md memory/curated/livy-memory-agent.md
git commit -m "docs(heartbeat): add enriched claims quality dashboard and rollout notes"
```

---

## Final Verification Gate (obrigatorio)

Antes de considerar concluído:

- [ ] `PYTHONPATH=. pytest tests/research/ -q` PASS
- [ ] `PYTHONPATH=. pytest tests/vault/ -q` PASS
- [ ] 1 ciclo de cron research executado sem erro
- [ ] validar distribuição de claims pós-run (amostra):

```bash
python3 - << 'PY'
import json
from collections import Counter
p='state/identity-graph/state.json'
claims=json.load(open(p)).get('claims',[])
c=Counter(x.get('claim_type') for x in claims if isinstance(x,dict))
t=sum(c.values()) or 1
print(c)
print({k:round(v*100/t,2) for k,v in c.items()})
PY
```

---

## Rollback Plan

Se houver degradação (explosão de `needs_review` ou regressão no cron):

1. Reverter commits da Task mais recente.
2. Manter apenas `status` extraction temporariamente (feature gate local no parser).
3. Rodar novamente `tests/research` + `tests/vault`.
4. Registrar incidente no `HEARTBEAT.md` e `memory/curated/livy-memory-agent.md`.
