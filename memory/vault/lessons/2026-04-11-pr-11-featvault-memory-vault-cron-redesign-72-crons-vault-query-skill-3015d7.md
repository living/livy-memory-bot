---
type: lesson
subject: "PR #11 — feat(vault): Memory Vault Cron Redesign — 7→2 crons + vault-query skill"
author: unknown
date: 2026-04-11
cycle_time: 1h 6m
tags: [operacionalização, observabilidade, cron, lock, circuit breaker]

## O que aconteceu
Este PR introduziu melhorias significativas no *Living Memory Vault*, incluindo a implementação de um lock compartilhado para evitar execuções concorrentes, um sistema de cursores para estado incremental, um mecanismo de circuit breaker para falhas consecutivas, e uma nova skill de documentação. Essas mudanças visam aumentar a confiabilidade e a observabilidade do sistema.

## Decisão / Solução
A equipe decidiu implementar um lock global para garantir que apenas uma execução do vault-ingest ou vault-lint ocorra por vez, além de adicionar cursores para rastrear o estado de cada fonte de dados. Um circuit breaker foi introduzido para lidar com falhas consecutivas, e logs estruturados foram implementados para melhor rastreabilidade. A documentação foi atualizada para incluir uma nova skill de consulta.

## Lessons
- Implementar locks compartilhados é crucial para evitar condições de corrida em sistemas que executam tarefas concorrentes.
- O uso de circuit breakers pode aumentar a resiliência do sistema, prevenindo falhas repetidas que podem causar problemas maiores.
- A documentação clara e acessível, como a skill de consulta, é essencial para facilitar a compreensão e o uso do sistema por outros desenvolvedores.

## Source
https://github.com/living/livy-memory-bot/pull/11
