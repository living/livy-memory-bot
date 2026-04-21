# SPEC: Enriquecimento de Claims — Decision & Linkage

**Data:** 2026-04-21
**Versão:** 1.1 (após review Livy Deep)
**Status:** spec
**Tipo:** feature (pipeline de memoria)
**Origem:** brainstorming 2026-04-21
**Review:** Livy Deep, 2026-04-21

---

## 1. Motivacao

O pipeline atual de research gera majoritariamente `claim_type=status` (98%+). Isso reduz o valor da memoria: status e volatil, nao captura decisoes ou relacoes entre entidades.

**Objetivo:** subir o percentual de `decision` e `linkage` para >=40% combinado, mantendo precisao atraves de confianca calibrada e triagem.

**Baseline atual (medido em 2026-04-21):**

| Metrica | Valor |
|---------|-------|
| `%status` | ~98% |
| `%decision` | ~1% |
| `%linkage` | ~1% |
| `%needs_review` | N/A (campo novo) |

---

## 2. Abordagem

Pipeline em 3 fases (A -> B -> C), incrementais e independentes:

| Fase | Foco | Entrega |
|------|------|---------|
| A | Extracao | Parsers enriquecem decision/linkage |
| B | Fusa + Confianca | Triagem, bonus cruzado, deduplicate |
| C | Observabilidade | KPIs, guardrails, alertas no HEARTBEAT |

**Perfil:** balanceado (2.5) -- boa precisao + volume visivel.
**Ambiguidade:** gera claim com `needs_review=true` quando confianca < 0.55 ou sem evidência.

---

## 3. Contrato Canônico de Claim

### 3.1 Claim `decision`

```python
@dataclass
class DecisionClaim:
    claim_type: Literal["decision"]
    entity_id: str                    # ID da entidade (meeting, PR, card, etc.)
    entity_type: str                  # "meeting", "pull_request", "project"
    text: str                         # Texto da decisao (obrigatorio, max 500 chars)
    source: str                       # "tldv", "github", "trello"
    source_ref: SourceRef             # URL + source_id
    event_timestamp: str              # ISO8601
    confidence: float                 # 0.0-1.0
    needs_review: bool = False
    review_reason: str | None = None  # "baixa_confianca", "sem_evidencia", "regex_incerto"
    decision_scope: str | None = None # "tech", "product", "ops"
    decision_owner: str | None = None # Login ou nome do responsible
    evidence_refs: list[SourceRef] = field(default_factory=list)
    audit_trail: list[AuditEntry] = field(default_factory=list)
```

### 3.2 Claim `linkage` (NOVO -- contrato completo)

```python
@dataclass
class LinkageClaim:
    claim_type: Literal["linkage"]
    entity_id: str                    # ID da entidade origem (PR, card, meeting)
    entity_type: str                  # "pull_request", "project", "meeting"
    from_entity: str                  # Entidade que faz a referencia
    from_entity_type: str             # Tipo da entidade origem
    to_entity: str                   # Entidade referenciada (PR#, card_id, meeting_id)
    to_entity_type: str              # Tipo da entidade destino
    relation: Literal[               # Enum fechado de relacoes
        "implements",    # Fecha/resolve issue ou card
        "blocks",       # Bloqueia outra entidade
        "depends_on",   # Depende de outra entidade
        "mentions",     # Menciona sem acao
        "discusses",    # Discute topico/reuniao
        "relates_to",   # Relacao generica
        "supersedes",   # Substitui versao anterior
    ]
    source: str                       # "github", "trello", "tldv"
    source_ref: SourceRef             # URL de origem
    event_timestamp: str              # ISO8601
    confidence: float                 # 0.0-1.0
    needs_review: bool = False
    review_reason: str | None = None
    evidence_refs: list[SourceRef] = field(default_factory=list)
    audit_trail: list[AuditEntry] = field(default_factory=list)
```

---

## 4. Fase A -- Extracao

### 4.1 TLDV Client (`vault/research/tldv_client.py`)

**Regra 1 -- `decisions` direto**
- Se `summaries[].decisions` tem conteudo, gera `claim_type=decision`.
- `event_timestamp` = `meeting.created_at`.
- `entity_id` = `meeting.id`.
- `text` = decisao crua.
- `confidence = 0.85` (fonte estruturada tem precisao alta).
- `evidence_refs` inclui ref para a reuniao.

**Regra 2 -- Deteccao por linguagem (fallback)**
- Padroes regex de linguagem decisoria em `topics` + `raw_text`:
  ```
  /(?:decidiu[-se]?|definido|acordado|vamos com|foi aprovado|aprovado|
       rejeitado|prioridade definida|bloqueado por|melhor e|\
       mudamos para|confirmado|estabelecido)\b/i
  ```
- **Contexto obrigatorio:** o padrao deve ocorrer em frase com pelo menos 5 palavras
  (evita hits isolados como "vamos" em "vamos verificar").
- Se encontrado: gera `decision` com `confidence = 0.45` + `needs_review=true`
  + `review_reason="regex_fallback"`.
- Se nao encontrado em reuniao com `decisions` vazio, **nao gera claim**.

**Regra 3 -- Linkage cruzado**
- Para cada URL/PR/card citada em `topics` ou `decisions`:
  - URL de PR: `linkage`, `relation=discusses`, `from_entity=meeting_id`, `to_entity=pr_number`.
  - Card Trello: `linkage`, `relation=mentions`, `from_entity=meeting_id`, `to_entity=card_id`.
  - Reuniao relacionada: `linkage`, `relation=relates_to`.

### 4.2 GitHub Parsers (`vault/research/github_parsers.py`)

**Regra 1 -- Status remain**
- PR aberto/fechado/merged -> `status` (mantem comportamento atual).

**Regra 2 -- Linkage de referencias**
- `GITHUB_REF_PATTERN` (ja existe) extrai refs do body.
- Mapeia para `linkage`:
  - `closes/fixes/resolve` -> `relation=implements`
  - `blocks` -> `relation=blocks`
  - Menciona sem acao -> `relation=mentions`
- Gera um `linkage` claim por ref extraida.
- Campos obrigatorios: `from_entity` (=PR number), `to_entity` (=ref number),
  `from_entity_type=pull_request`, `to_entity_type` inferido do tipo de ref.

**Regra 3 -- Decisoes por linguagem normativa**
- Padrao no body/PR title:
  ```
  /(?:^(?:feat|fix|docs|chore)\(|padrao passa a ser|\
       adotamos a partir de|implementar verso|mudar de|remover o|\
       depreciar o)\b/i
  ```
- Gera `decision` com `confidence = 0.55` + `needs_review=true`
  + `review_reason="linguagem_normativa"` se nao tiver label forte
  (`architecture`, `breaking-change`).

**Regra 4 -- Reviews com aprovacao direcional**
- Se review com `APPROVED` + comentario com pelo menos 10 palavras +
  pelo menos um dos verbos de decisao:
  - Gera `decision` com `confidence = 0.60`, `author` = reviewer login.

### 4.3 Trello Parsers (`vault/research/trello_parsers.py`)

**PRE-CONDICAO DE DADOS:** a regra 3 (comentarios/checklists) **exige**
que o Trello client traga esses campos na resposta da API. O parser deve
declarar explicitamente fallback quando esses campos estiverem ausentes.

**Regra 1 -- Status remain**
- Movimento de lista -> `status` (mantem).

**Regra 2 -- Linkage por URL**
- `GITHUB_PATTERN` no card description -> `linkage` (ja existe, manter).

**Regra 3 -- Decisoes por comentario/checklist**
- Para cada comentario no card (se `actions` disponivel na resposta API):
  - Aplicar regex de decisao (mesmo de 4.1 Regra 2).
  - Se encontrado E comentario tem >= 5 palavras:
    - `decision` com `confidence = 0.40` + `needs_review=true`
    - `entity_id` = card_id
    - `text` = texto do comentario
    - `review_reason="comentario_trello"`
- Para cada item de checklist marcado como "feito":
  - Se texto contem regex de decisao E >= 5 palavras:
    - Mesma logica de decision.
- **Fallback:** se `actions` nao estao na resposta, loga warning
  "trello_comments_unavailable" e pula a etapa de decisao por comentario
  (nao gera claim fantasma).

---

## 5. Fase B -- Fusa e Confianca

### 5.1 Metadata `needs_review`

Adicionar campos ao model de claim (em `vault/memory_core/models.py`):

```python
@dataclass
class Claim:
    # ... existing fields ...
    needs_review: bool = False
    review_reason: str | None = None  # "baixa_confianca"|"sem_evidencia"|"regex_fallback"|"comentario_trello"
```

### 5.2 Confianca calibrada

Em `vault/fusion_engine/confidence.py`, ajustar `compute_confidence`:

| Condicao | Ajuste |
|----------|--------|
| `claim_type=decision` com `evidence_refs` nao vazio | +0.15 bonus |
| `claim_type=linkage` com convergencia multi-fonte | +0.20 bonus |
| `claim_type=decision` sem evidência explícita | `needs_review=true`, `review_reason="sem_evidencia"` |
| Extraido por regex de linguagem (nao por campo estruturado) | -0.10 |
| `confidence` final < 0.55 | `needs_review=true` |

### 5.3 Algoritmo de Convergencia Multi-Fonte (para bonus de linkage)

"Evidencia cruzada" significa: o mesmo `to_entity` aparece em claims de
**2 ou mais fontes diferentes** dentro de uma janela de **7 dias**.

Implementacao:
```
convergence_key = SHA256(to_entity + relation)
fontes_unicas = set(c.source for c in recent_claims if c.to_entity == to_entity and c.relation == relation)
if len(fontes_unicas) >= 2:
    bonus +0.20 aplicado
```

onde `recent_claims` sao todos os claims dos ultimos 7 dias em `state/identity-graph/state.json`.

### 5.4 Deduplicacao semantica (separada de supersession)

**Dedup:** nao criar claim novo se chave ja existe com confianca >= 0.7.
**Supersession:** atualizar vinculo entre claims conflitantes.

Em `vault/research/state_store.py`, novas chaves:

```
decision_key:    SHA256(entity_id + "decision" + normalized_text_lower)
linkage_key:     SHA256(from_entity + relation + to_entity)
```

**Comportamento:**
- Se `decision_key` ja existe com confianca >= 0.7: **ignorar** (dedup).
- Se `linkage_key` ja existe: **ignorar** (dedup).
- **Nao aplicar supersession nesse caso** -- sao operacoes ortogonais.

### 5.5 Supersession para decision

Em `vault/fusion_engine/supersession.py`:

- `decision` só supersede `decision` anterior se:
  - Mesmo `entity_id` E
  - Similaridade de texto > 0.7 (usar `difflib.SequenceMatcher`)
    OU `supersession_reason` explicito no claim novo.
- `status` **nao supersede** `decision` (protege decisoes de serem
  sobrescritas por status).

---

## 6. Fase C -- Observabilidade

### 6.1 KPIs de qualidade

Adicionar ao cron `research-consolidation`:

```python
metrics = {
    "total_claims": len(new_claims),
    "by_type": Counter(c.claim_type for c in new_claims),
    "needs_review_count": sum(1 for c in new_claims if c.needs_review),
    "with_evidence": sum(1 for c in new_claims if c.evidence_refs),
}
pct = lambda v: (v / metrics['total_claims'] * 100) if metrics['total_claims'] else 0
```

**Thresholds:**

| Metrica | Alerta se |
|---------|-----------|
| `%decision` | < 15% por 2 ciclos |
| `%linkage` | < 25% por 2 ciclos |
| `%status` | > 60% por 2 ciclos |
| `%needs_review` | > 20% por 2 ciclos |
| `%with_evidence` | < 80% por 2 ciclos |

### 6.2 HEARTBEAT

Em `HEARTBEAT.md`, nova secao "Qualidade de Claims":

```
## Qualidade de Claims (research-consolidation)

| Metrica | Atual | Limiar | Status |
|---------|-------|--------|--------|
| decision% | X% | >=15% | ✅/🟡/🔴 |
| linkage% | X% | >=25% | ✅/🟡/🔴 |
| status% | X% | <=60% | ✅/🟡/🔴 |
| needs_review% | X% | <=20% | ✅/🟡/🔴 |
| with_evidence% | X% | >=80% | ✅/🟡/🔴 |
```

### 6.3 Alerta automatico

Se 2 ciclos consecutivos fora do threshold:
- Log `WARN: quality_guardrail_fail` no audit com `{metrica, atual, limiar, ciclo1_ciclo2}`
- Nota no HEARTBEAT: "Ajustar padrao regex em `<parser>`" ou "Investigar fonte `<source>`"

---

## 7. Prioridade de Implementacao (Ordem Tecnica)

| # | Arquivo | Fase | Prioridade |
|---|---------|------|-----------|
| 1 | `vault/memory_core/models.py` -- adicionar `needs_review` + `review_reason` | B | vermelho |
| 2 | `vault/research/trello_parsers.py` -- adicionar `needs_review` + regex + fallback comments/checklists | A | vermelho |
| 3 | `vault/research/github_parsers.py` -- linkage com `from/to_entity` completos + `needs_review` | A | vermelho |
| 4 | `vault/research/tldv_client.py` -- decisions direto + regex + linkage com `from/to_entity` | A | vermelho |
| 5 | `vault/fusion_engine/confidence.py` -- bonus e gates de `needs_review` | B | vermelho |
| 6 | `vault/fusion_engine/supersession.py` -- protecao decision vs status | B | amarelo |
| 7 | `vault/research/state_store.py` -- dedupe semantico decision_key/linkage_key (separado de supersession) | B | amarelo |
| 8 | `vault/crons/research_consolidation_cron.py` -- KPIs + alertas | C | azul |
| 9 | `HEARTBEAT.md` -- secao qualidade de claims | C | azul |

---

## 8. Testes

| Teste | Arquivo | Cobertura |
|-------|---------|-----------|
| `needs_review` setado corretamente | `tests/vault/test_claim_model.py` (novo) | confianca < 0.55, sem evidência, regex fallback |
| Bonus de confianca para decision com evidência | `tests/vault/fusion_engine/test_confidence.py` (expandir) | existing + novo bonus |
| Convergencia multi-fonte detecta 2+ fontes | `tests/vault/fusion_engine/test_confidence.py` (novo) | janela 7 dias, mesma to_entity |
| Deduplicate nao reinsere claim identico | `tests/vault/research/test_state_store.py` (expandir) | decision_key, linkage_key |
| Trello parser gera decision de comentario | `tests/research/test_trello_parsers.py` (expandir) | regex hit + sem hit + fallback comentarios ausentes |
| GitHub parser gera linkage de refs com campos completos | `tests/research/test_github_parsers.py` (expandir) | implements, blocks, mentions + from_entity/to_entity |
| TLDV client gera decision de summaries.decisions | `tests/research/test_tldv_client.py` (expandir) | populated, empty, regex hit |
| Guardrail alerta dispara corretamente | `tests/vault/ops/test_quality_guardrails.py` (novo) | 2 ciclos fora threshold |
| Supersession nao permite status sobrescrever decision | `tests/vault/fusion_engine/test_supersession.py` (expandir) | protecao ativa |

---

## 9. Riscos e Mitigacoes

| Risco | Prob | Impacto | Mitigacao |
|-------|------|---------|-----------|
| Volume excessivo de claims ruins | media | alto | `needs_review` + dedupe semantico |
| Decisoes falsas por regex | media | medio | contexto de 5 palavras minimas + `needs_review` + alta precisao no TLDV decisions |
| Supersessao excessiva | baixa | medio | Limitar supersession automatica a same claim_type + similarity > 0.7 |
| Performance degradada por deduplicacao complexa | baixa | baixo | Dedupe por SHA256 (O(1) lookup), nao por string diff |
| Trello comments ausentes na API | baixa | medio | Fallback explicito com log warning, pula etapa e nao gera claim fantasma |

---

## 10. Escopo fora

- Nao mexa no `vault/capture/` (transcricao Azure/Supabase).
- Nao mexa no `vault/insights/` (renderers, Weekly Insights).
- Nao mexa no schema do Supabase (tabelas TLDV).

---

## 11. Sucesso

- `%decision + %linkage` >= 40% em 30 dias apos deploy (vs baseline ~2%).
- `%needs_review` <= 20% apos tuning inicial.
- 0 alertas de qualidade por 7 dias consecutivos = feature madura.
- **Verificacao:** rodar query no SSOT apos 30 dias:
  ```sql
  SELECT claim_type, COUNT(*) FROM claims GROUP BY claim_type;
  ```
