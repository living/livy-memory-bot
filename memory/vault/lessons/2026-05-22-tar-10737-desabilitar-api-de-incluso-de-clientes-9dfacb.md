---
type: lesson
date: 2026-05-22
subject: "Trello: [TAR-10737] Desabilitar API de inclusão de clientes [B3/Listados]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3listados]
---

## O que aconteceu
Este PR foca em melhorar a rastreabilidade e previsibilidade do adapter ContasMAS e endurecer/ajustar comportamentos de criação/atualização de contas e subscriptions.

## Decisão / Solução
As principais entregas incluem deduplicação por checksum, logs mais ricos de Add/Update, uma nova regra configurável para a data de início de subscription e a desativação explícita das APIs de cadastro de contas, que agora retornam HTTP 410 Gone. A documentação interna também foi atualizada com “gotchas” e procedimentos de validação/execução via CLI.

## Lessons
- A deduplicação por checksum é uma abordagem eficaz para evitar a criação de registros duplicados.
- A desativação explícita de APIs obsoletas ajuda a manter a clareza e a previsibilidade nas interações com o sistema.

## Source
https://trello.com/c/xtnxdSOo
