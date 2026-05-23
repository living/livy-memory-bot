---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/24"
date: 2026-04-21
subject: "PR #24 — feat: enriched claims rollout (tasks 1-9)"
author: unknown
cycle_time: 3h 50m
tags: [feature, claims, pipeline, quality]

## O que aconteceu
Este PR implementa o rollout de **Enriched Claims (tasks 1–9)** no `livy-memory-bot`, evoluindo o modelo e a pipeline para capturar melhor **decisões**, **evidências**, **revisões humanas** e **deduplicação semântica**. Também melhora os parsers/clients (GitHub, Trello, TLDV), recalibra **confidence**, endurece regras de **supersession** e adiciona **guardrails de qualidade** no cron de consolidação.

## Decisão / Solução
Foram feitas várias modificações significativas, incluindo a adição de novos campos ao modelo de claims, melhorias nos parsers do GitHub e Trello, e a implementação de regras mais rigorosas para supersession e deduplicação semântica. Além disso, foram introduzidos guardrails de qualidade para monitorar a integridade das decisões.

## Lessons
- A implementação de revisões explícitas e motivos para claims melhora a auditabilidade e a transparência do sistema.
- A calibração da confiança deve ser cuidadosamente monitorada para evitar que claims com baixa confiança sejam priorizadas.
- A deduplicação semântica deve ser testada em diferentes cenários para garantir que todos os parsers estejam populando corretamente os dados necessários.

## Source
https://github.com/living/livy-memory-bot/pull/24
