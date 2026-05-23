---
type: lesson
subject: "PR #12 — feat(whisper): migrate to OmniRoute API, remove local faster-whisper"
author: unknown
tags: [API, segurança, resiliência]
date: 2026-04-04

## O que aconteceu
Este PR implementa a migração do Whisper para um fluxo API-first via OmniRoute, removendo a dependência de transcrição local (`faster-whisper`). Além disso, foram adicionadas funcionalidades de rerank e moderação, resultando em menos ruído e mais segurança.

## Decisão / Solução
A decisão foi migrar para uma abordagem API-first utilizando o OmniRoute, o que permitiu a remoção do `faster-whisper`. A implementação inclui um circuito breaker para aumentar a resiliência e uma moderação robusta para garantir a segurança dos dados.

## Lessons
- Sempre que possível, adote uma abordagem API-first para aumentar a flexibilidade e a escalabilidade do sistema.
- A implementação de circuit breakers é crucial para garantir a resiliência em sistemas que dependem de múltiplas APIs externas.
- A moderação de dados sensíveis deve ser uma prioridade em qualquer pipeline de processamento de informações para evitar vazamentos de PII.

## Source
https://github.com/living/livy-tldv-jobs/pull/12
