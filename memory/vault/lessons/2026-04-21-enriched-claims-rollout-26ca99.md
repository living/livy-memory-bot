---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/24"
date: 2026-04-21
subject: "PR #24 — Enriched Claims Rollout: quality guardrails + semantic deduplication"
author: lincolnqjunior
tags: [claims, quality-guardrails, deduplication, semantic-keys]

## O que aconteceu
PR #24 rollou o sistema de enriched claims com needs_review/review_reason, deduplicação semântica via decision_key/linkage_key, guardrails de qualidade com KPIs, e consolidação expandida. A validação pós-merge revelou que o quality guardrail ativa após 2 ciclos consecutivos ruins — e que o baseline legado (SSOT sem dados enriquecidos) conta como primeiro ciclo.

## Decisão / Solução
- **Quality guardrail**: `%decision >= 20%` e `%linkage >= 20%` como thresholds. Se ambos abaixo por 2 ciclos consecutivos, alerta. Baseline: `decision=0%`, `linkage=2.6%`, `status=97.4%` — primeiro ciclo ruim registrado.
- **Semantic deduplication keys**: `decision_key` (hash de `what_happened + subject`) e `linkage_key` (hash de `from/to_entity + type`) como gates secundários além do `content_key` — permite catch de duplicates que não são idênticos no texto.
- **needs_review / review_reason**: claims marcados automaticamente quando extraídos por regex fallback (em vez de LLM) ou quando a confiança está baixa.
- **Guardrail é sobre distribuição, não volume**: não é sobre ter mais claims, é sobre ter a proporção certa de decisões e linkages vs. status.

## Lessons
- Quality guardrail de 2 ciclos: o primeiro ciclo de alerta não envia notificação — só o segundo. Evita spam em transições de baseline.
- Baseline legado conta como ciclo 1: se o SSOT pré-enriched tem 0% decisions, qualquer implementação vai começar em ciclo ruim — é esperado e não é um bug.
- Semantic keys (decision_key, linkage_key) complementam content_key: duplicados perfeitos (mesmo texto) usam content_key; duplicates semânticos (mesma decisão, texto diferente) usam decision_key.
- A meta de `>=40%` para decision+linkage combinados é agressiva para um baseline de 2.6% — o pipeline vai demorar vários ciclos para convergir.

## Source
https://github.com/living/livy-memory-bot/pull/24
