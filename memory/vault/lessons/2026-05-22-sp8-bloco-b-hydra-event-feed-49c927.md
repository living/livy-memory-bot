---
type: lesson
date: 2026-05-22
subject: "Trello: SP8 Bloco B — Hydra Event Feed [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
O cartão representa a unificação da telemetria Hydra em um log de eventos, abordando tanto a comunicação de saída quanto a de entrada, com foco em idempotência e retenção de dados.

## Decisão / Solução
Foi decidido implementar uma tabela `svd.hydra_event_log` que captura toda a comunicação da Hydra, utilizando um novo endpoint para receber callbacks e garantindo a idempotência através de uma chave única. A retenção dos dados será gerenciada por meio de tarefas programadas com `pg_cron`.

## Lessons
- A implementação de um sistema de log append-only melhora a rastreabilidade e a integridade dos dados.
- A utilização de `correlationId` para garantir idempotência é crucial em sistemas que lidam com múltiplas fontes de eventos.

## Source
https://trello.com/c/yzcPNrBk
