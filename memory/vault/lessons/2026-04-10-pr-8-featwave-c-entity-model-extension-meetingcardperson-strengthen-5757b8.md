---
type: lesson
subject: "PR #8 — feat(wave-c): entity model extension — meeting+card+person strengthen"
author: unknown
date: 2026-04-10
cycle_time: 2h 8m
tags: [feature, architecture, observability]
---

## O que aconteceu
Este PR implementa a **Wave C** como uma expansão do modelo de domínio do Memory Vault, adicionando ingestões para **Meetings** e **Cards**, além de mecanismos de resolução de identidade e fortalecimento de `person` por sinais de participação. Também foram implementados novos relacionamentos e uma camada de observabilidade.

## Decisão / Solução
Foi decidido que a nova ingestão de entidades navegáveis incluiria um modelo conservador de resolução de identidade, com guardrails para evitar merges indesejados. A implementação de lint específico garante que os novos requisitos do modelo sejam atendidos, e a documentação foi atualizada para refletir as decisões arquitetônicas.

## Lessons
- A implementação de guardrails na resolução de identidade pode aumentar a segurança, mas também pode reduzir a automação, exigindo mais sinais para merges automáticos.
- A padronização de `source_keys` para cards é crucial para garantir a deduplicação em cenários multi-board, exigindo consistência em todo o pipeline.
- O novo lint pode causar falhas em pipelines existentes se entidades não atenderem aos novos requisitos, portanto, é importante revisar as entidades já existentes.

## Source
https://github.com/living/livy-memory-bot/pull/8
