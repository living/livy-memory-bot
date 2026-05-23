---
type: lesson
subject: "PR #17 — Evo Wiki Research Phase 2 — Trello stream + self-healing write-mode"
author: unknown
cycle_time: 23m
tags: [research, self-healing, Trello, metrics, documentation]
date: 2026-04-18

## O que aconteceu
Este PR expande o Evo Wiki Research adicionando uma nova fonte Trello ao pipeline de pesquisa e introduz um modo self-healing com várias funcionalidades de monitoramento e recuperação. Além disso, a documentação operacional foi atualizada para refletir essas mudanças.

## Decisão / Solução
Foi decidido integrar o Trello como uma nova fonte no pipeline de pesquisa, implementando um cliente específico para normalizar eventos e garantir idempotência. Também foi criado um sistema de self-healing para monitorar e auditar as decisões tomadas, além de um watchdog para o cron de consolidação, que valida métricas antes de executar.

## Lessons
- A integração de novas fontes de dados deve sempre considerar a idempotência e a normalização dos eventos para evitar colisões e garantir a consistência dos dados.
- Implementar um sistema de self-healing pode aumentar a resiliência do sistema, permitindo que ele se recupere automaticamente de falhas e mantenha a integridade dos dados.
- A documentação deve ser atualizada em paralelo com as implementações para garantir que todos os membros da equipe tenham acesso às informações mais recentes sobre o sistema.

## Source
https://github.com/living/livy-memory-bot/pull/17
