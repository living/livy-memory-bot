# SPEC: Enriquecimento de Claims — Decision & Linkage

**Data:** 2026-04-21  
**Versão:** 1.0  
**Status:** spec  
**Tipo:** feature (pipeline de memória)  
**Origem:** brainstorming 2026-04-21  

---

## 1. Motivação

O pipeline atual de research gera majoritariamente `claim_type=status` (98%+). Isso reduz o valor da memória: status é volátil, não capturam-se decisões ou relações entre entidades.

**Objetivo:** subir o percentual de `decision` e `linkage` para ≥40% combinado, mantendo precisão através de confiança calibrada e triagem.

---

## 2. Abordagem

Pipeline em 3 fases (A → B → C), incrementais e independentes:

| Fase | Foco | Entrega |
|------|------|---------|
| A | Extração | Parsers enrichecem decision/linkage |
| B | Fusão + Confiança | Triagem, bônus cruzado, deduplicate |
| C | Observabilidade | KPIs, guardrails, alertas no HEARTBEAT |

**Perfil:** balanceado (2.5) — boa precisão + volume visível.  
**Ambiguidade:** gera claim com `needs_review=true` quando confiança < 0.55 ou sem evidência.

---

## 3. Fase A — Extração

### 3.1 TLDV Client (`vault/research/tldv_client.py`)

**Regra 1 — `decisions` direto**
- Se `summaries[].decisions` tem conteúdo, gera `claim_type=decision`.
- `event_timestamp` = `meeting.created_at`.
- `entity_id` = `meeting.id`.
- `text` = decisão crua.

**Regra 2 — Detecção por linguagem (fallback)**
- Padrões regex de linguagem decisória em `topics` + `raw_text`:
  - `/(?:decidiu|definido|acordado|vamos|foi aprovado|aprovado|rejeitado|prioridade|bloqueado|melhor é|mudar para)\b/i`
- Se encontrado, gera `decision` com `confidence = 0.45` + `needs_review=true`.
- Se não encontrado em reunião com `decisions` vazio, não gera claim.

**Regra 3 — Linkage cruzado**
- Para cada PR/card/reunião citado em `topics` ou `decisions`:
  - Se URL de PR: `claim_type=linkage`, relation=`discusses`, `source_ref` aponta pro PR.
  - Se card Trello: `linkage`, relation=`mentions`.
  - Se reunião relacionada: `linkage`, relation=`relates_to`.

### 3.2 GitHub Parsers (`vault/research/github_parsers.py`)

**Regra 1 — Status remain**
- PR aberto/fechado/merged → `status` (mantém comportamento atual).

**Regra 2 — Linkage de referências**
- `GITHUB_REF_PATTERN` (já existe) extrai refs do body.
- Mapeia para `linkage`:
  - `closes/fixes/resolve` → relation=`implements`
  - `blocks` → relation=`blocks`
  - Menciona sem ação → relation=`mentions`
- Gera um `linkage` claim por ref extraída.

**Regra 3 — Decisões por linguagem normativa**
- Padrão no body/PR title:
  - `/(?:adotamos|padrão passa a ser|implementar|mudar para|remover|depreciar)\b/i`
- Gera `decision` com `confidence = 0.55` + `needs_review=true` se não tiver label forte.

**Regra 4 — Reviews com aprovação direcional**
- Se review com `APPROVED` + comentário com padrão de decisão (mesmos regex acima):
  - `decision` com `confidence = 0.60`, `author` = reviewer.

### 3.3 Trello Parsers (`vault/research/trello_parsers.py`)

**Regra 1 — Status remain**
- Movimento de lista → `status` (mantém).

**Regra 2 — Linkage por URL**
- `GITHUB_PATTERN` no card description → `linkage` (já existe, manter).

**Regra 3 — Decisões por comentário/checklist**
- Para cada comentário no card (se disponível na API response):
  - Aplicar regex de decisão. Se encontrado, gerar `decision` com:
    - `confidence = 0.40` + `needs_review=true`
    - `entity_id` = card_id
    - `text` = texto do comentário relevante
- Para cada item de checklist marcado como "feito":
  - Se texto contém padrão de decisão → `decision` (mesma lógica).

---

## 4. Fase B — Fusão e Confiança

### 4.1 Metadata `needs_review`

Adicionar campo ao model de claim (em `vault/memory_core/models.py`):

```python
@dataclass
class Claim:
    # ... existing fields ...
    needs_review: bool = False   # True if confidence < 0.55 or no evidence
    review_reason: str | None = None  # Why it needs review
```

### 4.2 Confiança calibrada

Em `vault/fusion_engine/confidence.py`, ajustar `compute_confidence`:

| Condição | Ajuste |
|----------|--------|
| `claim_type=decision` com `evidence_refs` não vazio | +0.15 bônus |
| `claim_type=linkage` com evidência cruzada (mesmo tópico em 2+ fontes) | +0.20 bônus |
| `claim_type=decision` sem evidência explícita | `needs_review=true`, `review_reason="sem_evidencia"` |
| Extraído por regex de linguagem (não por campo estruturado) | −0.10 |
| `confidence` final < 0.55 | `needs_review=true` |

### 4.3 Deduplicate semântica

Em `vault/research/state_store.py`, novas chaves de deduplicação:

```
decision_key:  SHA256(entity_id + claim_type + normalized_text_lower)
linkage_key:   SHA256(from_entity + relation + to_entity)
```

Se `decision_key` ou `linkage_key` já existe no SSOT com confiança ≥ 0.7, não inserir (supersede por convergência silenciosa).

### 4.4 Supersession para decision

Em `vault/fusion_engine/supersession.py`:

- `decision` só supersede `decision` anterior se:
  - Mesmo `entity_id` E
  - Similaridade de texto > 0.7 (usar `difflib.SequenceMatcher`) OU `supersession_reason` explícito.
- `status` não supersede `decision` (protege decisões de serem sobrescritas por status).

---

## 5. Fase C — Observabilidade

### 5.1 KPIs de qualidade

Adicionar ao cron `research-consolidation` (ou criar `vault-insights-quality-validate`):

```python
metrics = {
    "total_claims": len(new_claims),
    "by_type": Counter(c.claim_type for c in new_claims),
    "needs_review_count": sum(1 for c in new_claims if c.needs_review),
    "with_evidence": sum(1 for c in new_claims if c.evidence_ids),
}
pct = lambda k, v: (v / metrics['total_claims'] * 100) if metrics['total_claims'] else 0
```

**Thresholds:**

| Métrica | Alerta se |
|---------|-----------|
| `%decision` | < 15% por 2 ciclos |
| `%linkage` | < 25% por 2 ciclos |
| `%status` | > 60% por 2 ciclos |
| `%needs_review` | > 20% por 2 ciclos |
| `%with_evidence` | < 80% por 2 ciclos |

### 5.2 HEARTBEAT

Em `HEARTBEAT.md`, seção "Qualidade de Claims":

```
| research-consolidation | 07h | ✅/🟡/🔴 | decision=X% link=X% status=X% needs_review=X% |
```

### 5.3 Alerta automático

Se 2 ciclos consecutivos fora do threshold, o cron gera:
- Log `WARN: quality_guardrail_fail` no audit
- Nota no HEARTBEAT com recomendação: "Ajustar regex em `<parser>`" ou "Investigar fonte `<source>`"

---

## 6. Prioridade de Implementação (Ordem Técnica)

| # | Arquivo | Fase | Prioridade |
|---|---------|------|-----------|
| 1 | `vault/memory_core/models.py` — adicionar `needs_review` + `review_reason` | B | 🔴 |
| 2 | `vault/fusion_engine/confidence.py` — bônus e gates de `needs_review` | B | 🔴 |
| 3 | `vault/research/trello_parsers.py` — decisão por comentário/checklist | A | 🔴 |
| 4 | `vault/research/github_parsers.py` — linkage refs + decisão por linguagem | A | 🔴 |
| 5 | `vault/research/tldv_client.py` — decisions direto + fallback regex | A | 🟡 |
| 6 | `vault/fusion_engine/supersession.py` — supersession para decision | B | 🟡 |
| 7 | `vault/research/state_store.py` — dedupe semântico decision/linkage | B | 🟡 |
| 8 | `vault/crons/research_consolidation_cron.py` — KPIs + alertas | C | 🔵 |
| 9 | `HEARTBEAT.md` — seção qualidade de claims | C | 🔵 |

---

## 7. Testes

| Teste | Arquivo | Cobertura |
|-------|---------|-----------|
| `needs_review` setado corretamente | `tests/vault/test_claim_model.py` (novo) | confidence < 0.55, sem evidência |
| Bônus de confiança para decision com evidência | `tests/vault/fusion_engine/test_confidence.py` | existing |
| Deduplicate semântico não reinsere claim idêntico | `tests/vault/research/test_state_store.py` (expandir) | decision_key, linkage_key |
| Trello parser gera decision de comentário | `tests/research/test_trello_parsers.py` (expandir) | regex hit, no hit |
| GitHub parser gera linkage de refs | `tests/research/test_github_parsers.py` (expandir) | implements, blocks, mentions |
| TLDV client gera decision de summaries.decisions | `tests/research/test_tldv_client.py` (expandir) | populated, empty |
| Guardrail alerta dispara corretamente | `tests/vault/ops/test_quality_guardrails.py` (novo) | 2 ciclos fora threshold |

---

## 8. Riscos e Mitigações

| Risco | Prob | Impacto | Mitigação |
|-------|------|---------|-----------|
| Volume excessivo de claims ruins | média | alto | `needs_review` + dedupe semântico隔离 |
| Decisões falsas por regex | média | médio |阈值 0.55 + `needs_review` + alta precisão no TLDV decisions |
| Superação excessiva (supersession run-away) | baixa | médio | Limitar supersession automática a same claim_type + similarity > 0.7 |
| Performance degradada por deduplicação complexa | baixa | baixo | Dedupe por SHA256 (O(1) lookup), não por string diff |

---

## 9. Escopo fora

- Não mexe no `vault/capture/` (transcrição Azure/Supabase).
- Não mexe no `vault/insights/` (renderers, Weekly Insights).
- Não mexe no schema do Supabase (tabelas TLDV).

---

## 10. Sucesso

- `%decision + %linkage` ≥ 40% em 30 dias após deploy.
- `%needs_review` ≤ 20%稳定após tuning inicial.
- 0 alertas de qualidade por 7 dias consecutivos = feature madura.
