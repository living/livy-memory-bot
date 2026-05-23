---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/33"
date: 2026-05-20
subject: "PR #33 — fix(action-required): rate limiting, svdFetch retry, code format, correlationId"
author: unknown
cycle_time: 15m
tags: [API, Resiliência, Documentação]

## O que aconteceu
Este PR reforça a robustez e rastreabilidade na integração com o Hydra e melhora a resiliência do client web. As principais entregas incluem rate limiting em endpoints expostos, inclusão do CorrelationId no fluxo Hydra e implementação de retry com backoff no svdFetch do frontend.

## Decisão / Solução
Foi decidido implementar rate limiting em endpoints críticos para evitar abusos, adicionar CorrelationId para melhor rastreabilidade e tornar o cliente web mais resiliente com retries e idempotência nas requisições.

## Lessons
- Implementar rate limiting em endpoints sensíveis é crucial para evitar instabilidade por tráfego excessivo.
- A inclusão de um CorrelationId no fluxo de requisições melhora a rastreabilidade e a observabilidade dos eventos.
- A estratégia de retry com backoff e Idempotency-Key ajuda a evitar duplicidade e melhora a resiliência do cliente em situações de falha.

## Source
https://github.com/living/delphos-svd/pull/33
