---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/17"
date: 2026-04-18
subject: "PR #17 — Evo Wiki Research Phase 2: Trello streaming + circuit breaker + self-healing"
author: lincolnqjunior
tags: [trello, circuit-breaker, self-healing, idempotency]

## O que aconteceu
PR #17 introduziu streaming de eventos Trello, circuit breaker com thresholds configuráveis, e modo rollback-only para self-healing. Durante o review, dois bloqueantes foram encontrados e corrigidos antes do merge: (1) `build_trello_event_key()` retornava `trello:{action_id}` para evitar colisão cross-source; (2) `self_healing_metrics.json` foi adicionado ao .gitignore — não deve ser versionado.

## Decisão / Solução
- **Circuit breaker com thresholds**: cada fonte tem limites independentes de erro; quando ultrapassados, o pipeline pausa writes e entra em modo rollback-only (apenas lê, não escreve no SSOT).
- **Append-only rollback**: quando o modo write é desativado, o sistema continua lendo do vault e gerando events, mas não persiste state changes — garante que o SSOT não é corrompido.
- **Event key namespace**: `trello:{action_id}` em vez de `{action_id}` — evita colisão se outra fonte usar o mesmo ID.

## Contexto (opcional)
O self-healing do metrics file (.gitignore) lembra que ficheiros de estado de pipeline não devem ser versionados. O `state/identity-graph/` também está no .gitignore.

## Lessons
- Ficheiros de estado de pipeline (metrics, state.json) não são para versionar — fazem parte do runtime, não do repo.
- Event keys com namespace (`trello:`) evitam colisão cross-source em IDs que podrían ser reutilizados entre fontes.
- Circuit breaker com modo rollback-only preserva a integridade do SSOT: mesmo com falha de fonte, o sistema não corrompe dados.

## Source
https://github.com/living/livy-memory-bot/pull/17
