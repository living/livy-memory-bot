---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/23"
date: 2026-04-19
subject: "PR #23 — Self-Healing Apply V2: policy + circuit breaker + idempotência"
author: lincolnqjunior
tags: [self-healing, idempotency, circuit-breaker, schema-migration]

## O que aconteceu
PR #23 introduziu a política de apply V2 com thresholds calibrados, merge ID determinístico, e circuit breaker de 3 tiers. A infraestrutura está pronta para integração com o pipeline de research, mas a política de when-to-apply é controlada pelo pipeline chamador (o `apply_merge_to_ssot` não popula `decision['contradiction']` sozinho).

## Decisão / Solução
- **Política V2**: `>=0.85` auto-apply, `0.45-0.84` queued, `<0.45` dropped. A calibração reflete que hipóteses de alta confiança são seguras para aplicar automaticamente.
- **Merge ID determinístico**: `SHA256(hypothesis + confidence + source)` — o mesmo input gera sempre o mesmo ID, garantindo idempotência.
- **Circuit breaker 3-tier**: monitoring → write_paused → global_paused. Reset automático após 3 clean runs.
- **Schema migration in-place**: o schema do state.json é migrado de v1 para v2 sem downtime —新增 campos têm default, campos antigos são preservados.
- **Rollback append-only**: todas as operações de merge são logadas em `vault/logs/experiments.jsonl` — qualquer estado pode ser reconstruído.

## Lessons
- Merge ID baseado em hash (em vez de UUID) garante que o mesmo input gera o mesmo ID em qualquer instância — idempotência real entre runs.
- Schema migration in-place é possível se todos os novos campos tiverem defaults e os antigos forem preservados — nunca remover campos, só adicionar.
- Circuit breaker de 3 tiers permite resposta proporcional: primeiro alerta, depois pausa writes, finalmente pausa global.
- A responsabilidade de populate `contradiction` é do pipeline chamador, não do apply — decisões de fusão belong ao pipeline, não ao apply.

## Source
https://github.com/living/livy-memory-bot/pull/23
