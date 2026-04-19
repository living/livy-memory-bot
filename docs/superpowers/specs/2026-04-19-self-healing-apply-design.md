# SPEC: Self-Healing Apply Mode + Wiki v2 Observability (v2)

**Data:** 2026-04-19  
**Status:** revised-after-review  
**Owner:** Lincoln / Livy Memory

---

## 1) Contexto e decisões fechadas

Objetivo: evoluir o self-healing de **read-only evidence** para **apply automático em produção** no pipeline wiki v2.

Decisões já aprovadas:
- Aprovação: fully automatic
- Threshold principal: `confidence >= 0.85`
- Sem limite por execução
- Contradição forte também aplica se `>= 0.85`
- Abordagem: **inline no pipeline**

---

## 2) Ajustes críticos (alinhamento com código real)

### 2.1 Compatibilidade com modo agressivo legado (0.70–0.84)

Código atual (`vault/research/self_healing.py`) aplica 0.70–0.84 quando `SELF_HEALING_AGGRESSIVE_MODE=true` (default atual).

**Decisão desta spec:**
- Para wiki v2 apply mode, política oficial é **strict >= 0.85**.
- Faixa 0.70–0.84 deixa de auto-apply e passa para **queued** (ou skipped por policy), sem aplicar.
- `SELF_HEALING_AGGRESSIVE_MODE` fica **legado/deprecado** e não controla wiki v2 apply mode.

**Precedência de policy (explícita):**
1. `SELF_HEALING_POLICY_VERSION=v2` → strict 0.85+.
2. `SELF_HEALING_POLICY_VERSION=v1` (compat legado temporário) → comportamento antigo com faixa agressiva.
3. Se não declarado → assume **v1** (compatibilidade com estado atual).

**Rollout sequencial:**
- Fase 1: código com suporte a v2, mas default em código é `v1` (backwards compat).
- Fase 2: após estabilização, promover `v2` como default em código e remover flag de ambiente.
- Ativação explícita para produção: `SELF_HEALING_POLICY_VERSION=v2`.

> Plano: manter `v1` apenas para rollback temporário durante rollout; remover após janela de estabilização.

---

### 2.2 Estratégia de arquivo (evitar conflito)

Não criar `self_healing_apply.py` agora.

**Decisão:** evoluir o módulo existente `vault/research/self_healing.py`.

Motivo:
- Já centraliza thresholds, decisões e métricas.
- Já possui suíte ativa (`tests/research/test_self_healing_apply.py`, `test_circuit_breaker.py`, etc.).
- Menor risco de drift/import ambiguities.

---

### 2.3 Contrato concreto de integração no pipeline

Integração alvo: `vault/research/pipeline.py` no caminho wiki v2 (após `fuse()` e antes de persistência final).

#### Entrada do apply

```python
SelfHealingApplyInput = {
  "source": str,                 # github|trello|tldv
  "event_key": str,
  "entity_id": str,
  "winner_claim": dict,          # claim normalizada vencedora
  "loser_claim": dict | None,    # claim supersedida/contradita (se houver)
  "confidence": float,
  "contradiction": bool,
  "reason": str,
  "run_id": str,
}
```

#### Saída do apply

```python
SelfHealingApplyResult = {
  "decision": "applied"|"queued"|"dropped"|"skipped",
  "confidence": float,
  "policy_version": "v1"|"v2",
  "merge_id": str | None,
  "state_changed": bool,
  "reason": str,
}
```

#### Persistência no SSOT

`state/identity-graph/state.json` recebe `applied_merges[]` com idempotência por `merge_id`:

```json
{
  "merge_id": "sha256(source|entity_id|winner_claim_id|loser_claim_id|reason)",
  "applied_at": "2026-04-19T19:30:00Z",
  "source": "github",
  "event_key": "github:pr_merged:123",
  "entity_id": "person:github:foo",
  "winner_claim_id": "claim:...",
  "loser_claim_id": "claim:...",
  "confidence": 0.91,
  "contradiction": true,
  "reason": "supersession_by_newer_evidence",
  "policy_version": "v2"
}
```

Se `merge_id` já existir: não reaplica (idempotente), retorna `state_changed=false`.

---

### 2.4 Rollback (formato correto)

Rollback de wiki v2 deve usar patch JSON (não comando path solto):

```json
{
  "features": {
    "wiki_v2": {
      "enabled": false
    }
  }
}
```

Rollback específico do apply mode:

```bash
SELF_HEALING_POLICY_VERSION=v1
# ou
SELF_HEALING_WRITE_ENABLED=false
```

---

### 2.5 Unificação de métricas (sem schema duplicado conflitante)

Não criar métrica paralela conflitante sem estratégia.

**Decisão:** manter `state/identity-graph/self_healing_metrics.json` como arquivo canônico, com `schema_version: 2`.

#### Compat v1 + extensão v2 + regra de migração

Campos legados preservados:
- `applied`, `queued`, `dropped`, `skipped`, `dry_run`, timestamps

Campos v2 adicionados:
- `schema_version: 2`
- `hourly_24h`: série temporal por hora e por fonte
- `contradictions_detected`
- `supersessions_applied`
- `avg_confidence_by_source`
- `auto_rejected_below_threshold`
- `apply_errors`

**Regra de migração v1→v2:**
- Se `self_healing_metrics.json` existe e **não tem** `schema_version` → assumir `v1` e fazer upgrade in-place na primeira escrita v2.
- Upgrade in-place: ler estado existente, adicionar `schema_version: 2` e campos v2 faltantes (inicializados em zero), reescrever.
- Garantia: primeira escrita v2 nunca perde dados de runs anteriores.

Exemplo resumido:

```json
{
  "schema_version": 2,
  "applied": 12,
  "queued": 5,
  "dropped": 2,
  "skipped": 1,
  "hourly_24h": {
    "2026-04-19T18:00": {
      "github": {"contradictions_detected": 1, "supersessions_applied": 2, "avg_confidence": 0.89, "auto_applied_count": 2, "auto_rejected_below_threshold": 3, "apply_errors": 0}
    }
  }
}
```

---

## 3) Observability no HEARTBEAT (24h por hora)

HEARTBEAT passa a renderizar a partir de `self_healing_metrics.json` (schema v2):

- contradições detectadas
- supersessions aplicadas
- confiança média por fonte
- auto_applied_count
- auto_rejected_below_threshold
- apply_errors

Tabela por fonte (`github`, `trello`, `tldv`) + total + tendência 24h.

---

## 4) Requisitos operacionais adicionais

### 4.1 Lock transacional no state

Apply no SSOT deve executar sob lock existente do state store para evitar write races.

**Mecanismo:** `state_store.py` já usa `fcntl.flock()` com lock file `state/identity-graph/.lock`. A integração deve usar o mesmo `acquire_lock()` / `release_lock()` do `state_store`, não criar lock paralelo.

**Ordem de operações:**
1. `acquire_lock(lock_path)`
2. ler state
3. aplicar merge no dict
4. escrever state
5. `release_lock(lock_path)`

Se lock não puder ser adquirido após TTL (default 600s), o apply é **skipped** (não applied) e logado como `reason: lock-timeout`.

### 4.2 Idempotência

`merge_id` obrigatório por evento aplicado para evitar double-apply em retries/replays.

### 4.3 Pruning / retenção

- `applied_merges`: retenção 180 dias (alinhada ao state store)
- `hourly_24h`: janela deslizante (mantém só últimas 24 horas)

---

## 5) Plano de implementação (sem código ainda)

1. Atualizar `self_healing.py` para policy v2 (strict 0.85).
2. Implementar contrato `SelfHealingApplyInput/Result` no pipeline wiki v2.
3. Adicionar idempotência (`merge_id`) + lock de escrita no state.
4. Migrar métricas para `schema_version: 2` mantendo compat com campos legados.
5. Atualizar render do HEARTBEAT com série 24h por fonte.
6. Cobertura TDD:
   - policy v2 vs v1
   - contradição >=0.85 aplica
   - idempotência (replay não duplica)
   - lock/write race
   - métricas v2 + render HEARTBEAT

---

## 6) Critérios de aceite

- Apply automático ocorre somente para `confidence >= 0.85` em policy v2.
- Faixa 0.70–0.84 não auto-aplica em v2.
- `applied_merges` é idempotente (`merge_id`) e auditável.
- HEARTBEAT mostra observability wiki v2 por fonte (24h/hora).
- Rollback funcional via patch JSON de config + fallback de policy/env.
