# Design: Shadow-to-Evolution Pipeline — Auto-Curation V2

**Versão:** 1.0
**Data:** 2026-04-09
**Status:** Aprovado (Lincoln)
**Referência:** baseado em https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f

---

## Resumo

Pipeline evolutivo de curadoria que aprende com cada ciclo de shadow reconciliation. Prioridades: **qualidade > ruído > feedback learning > promoção**. Zero falso positivo por semana como hard gate. Fully auditable, TDD-first, com fact-checking via Context7 + documentação oficial.

---

## 1. Arquitetura de Alto Nível

```
SINAIS (TLDV + GitHub + Logs + Feedback)
        │
        ▼
┌─────────────────────────────────────────────┐
│  INGESTÃO (existente: collectors + bus)      │
└─────────────────┬───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  SHADOW DETECTOR (existente + melhorado)    │
│  • Causal graph builder                     │
│  • Confiança por evidência cruzada          │
│  • Deduplicação por fingerprint            │
└──────────┬──────────────┬──────────────────┘
           │              │
           ▼              ▼
  ALTA CONFIANÇA    BAIXA CONFIANÇA
  (>threshold)       (<threshold)
           │              │
           ▼              ▼
  AUTO-PROMOTE       TRIAGE BRIDGE
  (write-mode)       → Mattermost
                     (LLM pre-filter + scoring)
                              │
                              ▼
                      RESOLUÇÃO HUMANA
                      (approve/reject)
                              │
                              ▼
                    FEEDBACK → CONFIDENCE ENGINE
                              │
                              ▼
                     TELEGRAM SUMMARY + OVERRIDE
```

**Princípios de design:**
- Cada camada é independente e testável.
- Artefatos append-only (ledger, triage-decisions, promotion-events).
- correlation_id único por ciclo para rastreabilidade completa.

---

## 2. Política de Decisão (Zero FP como Regra)

### 2.1 Gate de Promoção (Shadow → Write)

Promoção automática requer **todos** os critérios:

| # | Critério | Threshold | Origem |
|---|---|---|---|
| 1 | Causal completeness | ≥ 0.85 | Causal graph builder |
| 2 | Evidência cruzada | ≥ 2 fontes distintas | signal collectors |
| 3 | Risk tier | Tier A (baixo risco) | Classificador |
| 4 | Conflitos | 0 conflitos ativos | Conflict detector |
| 5 | Divergência histórica | < threshold | Last-N cycles check |

Se qualquer critério falhar → vai para **triage Mattermost**.

### 2.2 Risk Tier Classification

| Tier | Descrição | Elegível para auto-promotion | Exemplo |
|---|---|---|---|
| **A** | Mudanças estruturadas e reversíveis | ✅ Sim (com gate) | Status transition, referência, metadata |
| **B** | Síntese textual curta com alta evidência | ❌ Não | Resumo de decisão, nota contextual |
| **C** | Mudanças interpretativas amplas | ❌ Não (manual obrigatório) | Decisões estratégicas, merges semânticos grandes |

### 2.3 SLO (Service Level Objectives)

| Métrica | Target | Gate |
|---|---|---|
| Falso positivo | 0 / semana | Hard gate — bloqueia auto-promotion |
| Ruído (duplicação) | < 5% por ciclo | Alerta se > 3% |
| Deferred por falta causal | Redução de 30% em 2 semanas | Tracking por ciclo |
| Auto-promotion rate | Aumento gradual (pós-estabilidade) | Só após 2 semanas com FP=0 |

---

## 3. Loop Evolutivo de Aprendizado

### 3.1 Fluxo de Triagem

1. Shadow classifica candidatos em: `auto`, `triage`, `reject`.
2. Candidatos `triage` → Mattermost com payload estruturado:
   - `decision_id`, `topic`, `evidences`, `confidence_breakdown`, `risk_tier`, `proposal`
3. **LLM pre-filter** no Mattermost:
   - Remove duplicados
   - Agrupa similares
   - Sugere prioridade
4. Humano decide: `approve` / `reject` / `needs_context`.
5. Sistema grava decisão em:
   - `triage-decisions.jsonl`
   - `reconciliation-ledger.jsonl` (update do registro)
6. **Telegram** recebe:
   - Resumo do ciclo com contagens
   - Botão `override_hold` (força hold manual)
   - Botão `override_promote` (força promoção com justificativa obrigatória)

### 3.2 Aprendizado Incremental (Sem Drift)

- Decisões humanas alimentam `feedback_buffer`.
- Ajuste de regra/threshold **só após**:
  - Mínimo de 20 amostras acumuladas.
  - Replay offline no dataset histórico.
  - Teste de não-regressão (TDD).
- Threshold ajusta em passos pequenos (max ±0.05 por ciclo).
- Rollback automático se FP > 0 detectado.

### 3.3 Calibrador de Confiança

Módulo `confidence_calibrator.py`:
- Mantém registro de: `evidence_type`, `source_count`, `causal_depth`, `conflict_count` → `actual_precision`.
- Re-calibra a cada ciclo com feedback.
- Usa regressão simples para estimar `causal_completeness` real.

---

## 4. TDD-First + Auditabilidade Fim-a-Fim

### 4.1 Estratégia TDD (ordem de implementação)

```
Phase 1 — Unit Tests
  ├── test_causal_scorer.py          (unit)
  ├── test_deduplicator.py           (unit)
  ├── test_tier_classifier.py        (unit)
  └── test_confidence_calibrator.py  (unit)

Phase 2 — Contract Tests
  ├── test_signal_event_schema.py    (schema validation)
  ├── test_ledger_entry_schema.py    (schema validation)
  └── test_triage_payload_schema.py (schema validation)

Phase 3 — Replay Tests
  └── test_replay_10_real_cases.py  (dataset: os 10 casos R005)

Phase 4 — Safety Tests
  └── test_zero_fp_gate.py          (garante: missing criteria → never promote)

Phase 5 — Integration Tests
  ├── test_shadow_to_triage_bridge.py
  └── test_feedback_ingest_loop.py
```

### 4.2 Fact-Checking com Context7 + Documentação Oficial

**Antes de qualquer promoção automática**, o sistema consulta:

1. **Context7 API** — para buscar documentação técnica relevante do domínio (ex.: OpenClaw, Supabase, GitHub API).
2. **Fontes oficiais** — GitHub API, docs do Supabase, APIs conhecidas.
3. **Topic files existentes** — para verificar consistência com estado atual.

Se fact-check **falhar** (informação contraditória ou não verificável) → candidate vai para `triage` com flag `fact_check_failed`.

```python
context7_client = Context7Client(api_key=os.environ["CONTEXT7_API_KEY"])

def fact_check(decision_candidate: DecisionCandidate) -> FactCheckResult:
    query = f"{decision_candidate.topic} {decision_candidate.description}"
    results = context7_client.search(query=query, max_results=3)
    return FactCheckResult(
        verified=len(results) > 0,
        sources=[r["url"] for r in results],
        contradictions=_find_contradictions(decision_candidate, results)
    )
```

### 4.3 Auditabilidade

Artefatos append-only (nunca reescritos):

| Artefato | Formato | Conteúdo |
|---|---|---|
| `reconciliation-ledger.jsonl` | JSONL | Decisões do ciclo + scores |
| `reconciliation-report.md` | Markdown | Resumo por ciclo |
| `triage-decisions.jsonl` | JSONL | Ações humanas/LLM no triage |
| `promotion-events.jsonl` | JSONL | Promoções reais (somente) |
| `model-threshold-changelog.md` | Markdown | Histórico de ajustes de threshold |
| `fact-check-log.jsonl` | JSONL | Resultados de fact-check por candidate |

**Cada promoção responde:**
- Qual evidência?
- Qual regra?
- Qual score?
- Quem aprovou?
- Qual fact-check foi executado?
- Qual rollback path?

---

## 5. Riscos, Mitigação, Resiliência e Quick Wins

### 5.1 Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|---|---|---|---|
| Overfitting ao feedback humano recente | Média | Alto | Replay set fixo + janela mínima de validação (20 amostras) |
| LLM pre-filter "inventar" contexto | Média | Alto | Só aceita evidência com referência URL verificável |
| Ruído por duplicação persistente | Alta | Médio | Fingerprint semântico + dedup por janela 7d |
| Falha de canal (Mattermost/Telegram) | Baixa | Alto | Fila local durável + retry/backoff + dead-letter |
| Regressão silenciosa de qualidade | Baixa | Alto | SLO gate (FP=0) bloqueia auto-promotion |
| Fact-check Context7 indisponível | Média | Baixo | Fallback: aceita candidate com flag `fact_check_pending` → triagem manual |

### 5.2 Resiliência Operacional

- **Idempotência**: promoções usam `upsert` por `decision_id` — retry seguro.
- **Fallback de triage**: se Mattermost indisponível → mantém shadow + registra `triage_pending`.
- **Circuit breaker**: para APIs externas (Context7, GitHub) — 3 falhas = breaker open por 5min.
- **Healthchecks por estágio**: `ingest_ok`, `score_ok`, `triage_ok`, `feedback_ok`, `promote_ok`.

### 5.3 Quick Wins (Cronograma)

**48 horas**
1. Score breakdown explícito por decisão no ledger JSONL.
2. Dedup por fingerprint + janela 7d (testado com replay dos 10 casos).
3. Telegram summary com botão `override_hold`.

**7 dias**
4. Mattermost bridge com payload JSON estruturado.
5. LLM pre-filter com regra "evidence-only" (sem gerar contexto).
6. Replay test suite com os 10 casos R005 (validação de não-regressão).

**14 dias**
7. Calibrador de threshold com feedback validado.
8. Auto-promotion Tier A com gate completo (5 critérios).
9. Dashboard de métricas (qualidade/ruído/deferred/promoted por ciclo).

---

## 6. Componentes e Arquivos

### 6.1 Componentes novos

| Componente | Responsabilidade |
|---|---|
| `causal_scorer.py` | Calcula causal completeness e evidence cross-score |
| `fact_checker.py` | Consulta Context7 + docs oficiais antes de promoção |
| `deduplicator.py` | Fingerprint semântico + janela temporal |
| `tier_classifier.py` | Classifica Tier A/B/C |
| `confidence_calibrator.py` | Aprende de feedback e ajusta thresholds |
| `triage_bridge.py` | Envia para Mattermost + gerencia resposta |
| `mattermost_client.py` | Wrapper para API Mattermost |
| `telegram_override_handler.py` | Processa botões override do Telegram |

### 6.2 Arquivos de teste

| Teste | Tipo |
|---|---|
| `test_causal_scorer.py` | Unit |
| `test_deduplicator.py` | Unit |
| `test_tier_classifier.py` | Unit |
| `test_confidence_calibrator.py` | Unit |
| `test_signal_event_schema.py` | Contract |
| `test_ledger_entry_schema.py` | Contract |
| `test_triage_payload_schema.py` | Contract |
| `test_replay_10_real_cases.py` | Replay |
| `test_zero_fp_gate.py` | Safety |
| `test_shadow_to_triage_bridge.py` | Integration |
| `test_feedback_ingest_loop.py` | Integration |

### 6.3 Artefatos de runtime

| Arquivo | Local |
|---|---|
| `reconciliation-ledger.jsonl` | `memory/` |
| `reconciliation-report.md` | `memory/` |
| `triage-decisions.jsonl` | `memory/` |
| `promotion-events.jsonl` | `memory/` |
| `model-threshold-changelog.md` | `memory/` |
| `fact-check-log.jsonl` | `memory/` |

---

## 7. Integração com Existing Pipeline

O `curation_cron.py` existente é extendido, não substituído:

```
curation_cron.py (existing flow)
  ├── 1-2. signals → (UNCHANGED)
  ├── 3. reconciliation → ENHANCED
  │     ├── deduplicator (NEW)
  │     ├── causal_scorer (NEW)
  │     ├── tier_classifier (NEW)
  │     └── fact_checker (NEW)
  ├── 4. auto-curate → GATED
  │     ├── if tier==A AND all criteria → promote
  │     └── if else → triage bridge
  ├── 5. triage → ENHANCED
  │     ├── mattermost_client
  │     └── telegram_override_handler
  └── 6. feedback learn → ENHANCED
        ├── confidence_calibrator (NEW)
        └── model-threshold-changelog.md
```

---

## 8. Dependências

| Dependência | Uso |
|---|---|
| `CONTEXT7_API_KEY` | Fact-checking (`.env`) |
| Mattermost webhook/integration | Triage bridge |
| `feedback-log.jsonl` (existente) | Feedback learning loop |
| `learned-rules.md` (existente) | Contexto de regras aprendidas |

---

## 9. Out of Scope (YAGNI)

- Multi-tenant / multi-workspace.
- Promoções automáticas de Tier B ou C.
- Alteração de schema de topic files por agente (só additions/mutations de decisão).
- RAG vetorial (topic files já funcionam como memória estruturada).
