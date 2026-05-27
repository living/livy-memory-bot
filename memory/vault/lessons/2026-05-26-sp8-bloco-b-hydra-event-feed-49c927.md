---
type: lesson
date: 2026-05-26
subject: "Trello: SP8 Bloco B — Hydra Event Feed [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
O objetivo deste cartão é unificar a telemetria do Hydra, tanto inbound quanto outbound, em uma tabela chamada `svd.hydra_event_log`. Isso inclui a implementação de proveniência, idempotência através do `correlationId`, e uma retenção de dados de 30 dias utilizando `pg_cron`.

## Decisão / Solução
A arquitetura proposta utiliza uma tabela append-only para registrar toda a comunicação do Hydra. Um novo endpoint anônimo foi criado para receber callbacks, garantindo idempotência através de uma chave única composta por `(direction, correlation_id, event_type)`. A retenção de dados será gerenciada por meio de uma rotina diária de DELETE via `pg_cron`.

## Lessons
- A implementação de um sistema de idempotência é crucial para evitar duplicações de eventos em sistemas distribuídos.
- A utilização de uma tabela append-only facilita a auditoria e a rastreabilidade das comunicações no sistema.

## Source
https://trello.com/c/yzcPNrBk
