---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/18"
date: 2026-04-18
subject: "PR #18 — Batch-first research clients + cadence wiring"
author: lincolnqjunior
tags: [research, cadence, batch, architecture]

## O que aconteceu
PR #18 introduziu clientes batch-first para GitHub, Trello e TLDV, e integrou cadence management no pipeline principal. Durante o review, 6 correções foram aplicadas antes do merge: fallback inválido em research_trello_cron (360 em vez de 20), filtro temporal no first-run do tldv_client, fluxo robusto em 2 etapas no github_client, contrato de cadence documentado como global (não per-source), logging estruturado em falhas, e wiring de record_budget_warning/record_healthy_run no pipeline.

## Decisão / Solução
- **Cadence global**: o CadenceManager gere um cadence global partilhado por todas as fontes — não há cadence por fonte. Cada fonte respeita o mesmo lock e a mesma política de retry.
- **Estado derivado por fonte**: cada fonte mantém `.research/<source>/state.json` como cache derivável — o SSOT permanece a fonte canónica de truth.
- **Two-step GitHub flow**: primeiro `search/issues` para encontrar PRs, depois `repos/{owner}/{repo}/pulls/{number}` para garantir `merged_at`, `merged`, `repo` e `author` estáveis — evita dependência de campos que variam entre endpoints.
- **Fallback de lookback sempre aplicado**: mesmo no first-run, o filtro temporal de 7 dias é aplicado — garante que não há comportamento diferente entre primeiro e subsequentes runs.

## Lessons
- Cadence é global: se uma fonte está em率高, todas pagam o custo — diseñar para independent failures.
- Filtros temporais devem funcionar no first-run igual a runs subsequentes — se há lookback, ele existe desde o início.
- Two-step flow para GitHub: o endpoint de search não retorna todos os campos necessários para o pipeline — usar search para discovery e pulls para detail.
- O estado derivado (`.research/<source>/`) é cache descartável — o SSOT é sempre a verdade.

## Source
https://github.com/living/livy-memory-bot/pull/18
