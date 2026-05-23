---
type: lesson
subject: "PR #23 — feat: self-healing apply v2 policy + deterministic merge id + SSOT persistence"
author: unknown
date: 2026-04-19
cycle_time: 19m
tags: [self-healing, policy, SSOT, idempotência, merge_id]

## O que aconteceu
Este PR evolui o Self-Healing para suportar uma policy v2 (strict) e introduz o esqueleto de apply com persistência no SSOT, utilizando um identificador determinístico (merge_id) e lock. A função apply_decision() agora retorna metadados de policy e um merge_id, e uma nova função apply_merge_to_ssot() foi adicionada para registrar merges aplicados.

## Decisão / Solução
Foi decidido implementar uma nova política de auto-aplicação que é mais rigorosa, onde apenas decisões com confiança igual ou superior a 0.85 são aplicadas. Além disso, a persistência no SSOT foi aprimorada com um mecanismo de lock e idempotência, garantindo que merges não sejam duplicados e que o sistema mantenha um histórico auditável.

## Lessons
- Implementar políticas de decisão rigorosas pode reduzir o risco de auto-aplicações indesejadas, melhorando a segurança do sistema.
- A introdução de um identificador determinístico (merge_id) deve ser cuidadosamente planejada para evitar colisões semânticas e garantir a consistência dos dados.
- A persistência auditável e o uso de locks são fundamentais para evitar condições de corrida e garantir a integridade dos dados em sistemas concorrentes.

## Source
https://github.com/living/livy-memory-bot/pull/23
