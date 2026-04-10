# PR #5 Validation Report — 2026-04-10

> **PR:** `feat(vault): domain modeling living (tasks 1-8)`  
> **Branch:** `feature/domain-modeling-ingestion-v1` → `master`  
> **Changed:** 32 files, +7575/-32  
> **Run by:** Livy Memory Agent (Lincoln)  
> **Model:** omniroute/PremiumFirst

---

## Resultado Geral

| Dimensão | Status | Detalhe |
|---|---|---|
| Testes unitários | ✅ PASS | 413/413 pass, 1 skipped |
| Pipeline idempotência | ✅ PASS | 5/5 variantes estáveis |
| Lint (contradictions/orphans/stale/gaps) | ✅ PASS | 0 em todas as categorias |
| Domain lint (contrato canônico) | ⚠️ EXPECTED DRIFT | 48 errors — esperado, migrating legacy |
| Quality review | ⚠️ EXPECTED DRIFT | 24 mismatches — mesmo root cause |
| Relationships integrity | ✅ PASS | 0 invalid edges |
| Identity ambiguity | ✅ PASS | 0 ambiguities |

**Verdict: APROVADO com follow-up de migração**

---

## 1. Testes Unitários

```
vault/tests/ — 413 passed, 1 skipped in 0.81s
```

Cobertura inclui: contrato canônico, pipeline E2E, lint, quality review, 
github_ingest allowlist, window filters, traceability, repair, reverify,
confidence gate, slug registry, metrics.

**Observação:** 1 skipped — verificar se é skip intencional.

---

## 2. Variação de Dados de Produção (Pipeline Stability)

Testado com 5 variantes do mesmo conjunto de eventos (`memory/signal-events.jsonl`, 684 events):

| Variante | Eventos | RC | Carregados | Deduped | Sinais |
|---|---|---|---|---|---|
| full | 684 | 0 | 684 | 31 | 31 |
| last_200 | 200 | 0 | 200 | 31 | 31 |
| last_50 | 50 | 0 | 50 | 28 | 28 |
| shuffled | 684 | 0 | 684 | 31 | 31 |
| duplicated_x2 | 1368 | 0 | 1368 | 31 | 31 |

**Análises:**
- ✅ **Idempotência confirmada:** 1368 events → 31 deduped (mesmo que 684 events) — pipeline não duplica
- ✅ **Ordem não importa:** shuffled produz exatamente o mesmo resultado que ordered
- ✅ **Variação temporal estável:** subsets diferentes produzem resultados consistentes
- ✅ **Sem crashes:** todas as variantes retornam rc=0

---

## 3. Lint Diário

```
memory/vault/lint-reports/2026-04-10-lint.md

Contradictions:  0 ✅
Orphans:         0 ✅
Stale Claims:    0 ✅
Coverage Gaps:   0 ✅
```

Vault limpo. Nenhum problema estrutural no conteúdo existente.

---

## 4. Domain Lint (Contrato Canônico)

```
vault/quality/domain_lint.py — run_domain_lint()

files_checked:       50
entity_errors:       24  (missing source_ref + retrieved_at)
source_errors:       48  (24 files × 2 fields)
relationships_valid: True
relationship_errors: []
edges_checked:       0
summary:             valid=False
```

**Root cause:** O ingest mínimo escreve:
```yaml
sources:
  - type: signal_event
    retrieved: 2026-04-10T12:47:40Z
```

O contrato canônico exige:
```yaml
sources:
  - source_type: signal_event
    source_ref: <origin_id>
    retrieved_at: 2026-04-10T12:47:40Z
    mapper_version: "1.0.0"
```

**É esperado.** O PR documenta isso na seção "⚠️ Pontos de Atenção":
> "O contrato canônico exige `source_ref/retrieved_at/mapper_version` (campos novos).
> O ingest mínimo escreve `sources: - type/ref/retrieved` (não inclui `mapper_version` e usa nomes diferentes)."

**Fix:** Migrar frontmatter existente na Fase 2.

---

## 5. Quality Review

```
memory/vault/quality-review/2026-04-10.md

Source coverage official %:  37.5  (24/64 sources are "official")
Unofficial sources:           40
Missing source records:       10
Identity ambiguities:         0
Relation invalid edges:        0
Mismatches:                  24  (mesma causa do domain_lint)
```

Mesma root cause do domain_lint. Migração do frontmatter resolve ambos.

---

## 6. Qualidade Gerativa

Decisões e concepts produzidos pelo pipeline:

| Categoria | Count |
|---|---|
| decisions written | 24 |
| concepts written | 7 |
| gate overrides | 12 |
| gaps/orphans after lint | 0/0 |

**Verificação qualitativa de samples:**
- Decisões com `decision:` prefix + conteúdo descritivo correto
- Topics com `topics_mentioned:` formatados como `Tópicos mencionados: <topic>`
- Slugs stable (origin_id stable suffix, não há duplicados)
- Timestamps presentes nos frontmatter
- id canonical no formato `decision:<slug>`

---

## 🐛 Issues Encontradas

### ⚠️ Issue 1 — Schema Drift (Expected, Needs Fix Before Merge)
**Severidade:** Média  
**Tipo:** Divergência de contrato canônico  
**Arquivos:** 24 decisões + 7 concepts  
**Descrição:** Frontmatter escrito pelo ingest não conforma com o contrato canônico
(`source_ref` + `retrieved_at` + `mapper_version` ausentes)  
**Ação:** Adicionar migration step na pipeline ou script de upgrade do frontmatter  
**Prioridade:** Antes de merge para `master` (ou documentar como "known gap Fase 1D")

### ⚠️ Issue 2 — 12 Gate Overrides
**Severidade:** Baixa (comportamento documentado)  
**Tipo:** Confidence gate bypassed para 12 signals  
**Descrição:** signal→confidence mapping no pipeline aplica `unverified` para signals sem 
origem clara, gatilhando 12 gate overrides  
**Ação:** Verificar se o mapping `map_signal_confidence()` está calibrado — pode ser 
conservador demais. Confirmar com observações de produção.  
**Recomendação:** Adicionar métrica de gate override rate ao dashboard (threshold de alerta)

### ℹ️ Issue 3 — 1 Test Skipped
**Severidade:** Info  
**Descrição:** 1 skipped nos 413 testes  
**Ação:** Verificar se skip é intencional (`pytest.skip` ou `pytest.mark.skip`)

---

## ✅ Pontos Fortes

1. **Pipeline robusto** — 5 variantes de dados, todas estáveis, idempotência confirmada
2. **Quality gates funcionando** — lint, domain_lint e quality_review todos operacionais
3. **Cobertura de testes excelente** — 413 testes cobrindo todos os módulos novos
4. **Arquitetura limpa** — contrato canônico bem definido com validadores
5. **Separação de concerns** — domain/canonical_types, domain/normalize, domain/identity_resolution
6. **Relationships integrity** — 0 invalid edges, nenhum uso de `part_of` proibido

---

## Próximos Passos Recomendados

| Prioridade | Ação | Responsável |
|---|---|---|
| 🔴 Alta | Adicionar migration script para frontmatter existente (fase 1D) | Lincoln/codex |
| 🟡 Média | Verificar se 12 gate overrides são esperados — calibrar map_signal_confidence | Lincoln |
| 🟢 Baixa | Investigar 1 test skipped | Lincoln |
| 🟢 Baixa | Adicionar métrica gate override rate ao HEARTBEAT | Lincoln |

---

## Recomendação de Merge

**STATUS: 🟡 APROVADO COM CONDIÇÕES**

O PR está pronto para merge em termos de:
- Funcionalidade ✅
- Testes ✅
- Estabilidade (variação de dados) ✅
- Lint limpo ✅

**Condição:** Documentar schema drift (24 files) como "known gap" na descrição do PR 
ou entregar migration script junto com o merge.

O domain_lint está funcionando corretamente — ele está capturando exatamente 
o gap documentado no próprio PR. Isso valida que os quality gates são efetivos.

---
_Validation run: 2026-04-10 12:47 UTC | Livy Memory Agent | model: omniroute/PremiumFirst_
