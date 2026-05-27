---
type: lesson
date: 2026-05-26
subject: "Trello: [TAR-11494] Estão subindo somente valores positivos no Vendas_SAP [B3/UIF+NW+NT]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3uifnwnt]
---

## O que aconteceu
Recebemos o acionamento da Jenifer e Caroline que os Num_Docs 96025 e 96026 subiram no Vendas_SAP somente os valores positivos, sendo que não deveria subir nada pois o valor negativo neta o valor positivo.

## Decisão / Solução
Foi decidido que a lógica de subida dos valores no Vendas_SAP deve ser revisada para garantir que, em casos de valores negativos e positivos, os negativos sejam considerados e não permitam a subida de dados incorretos.

## Lessons
- A importância de validar a lógica de processamento de dados antes da subida para evitar inconsistências.
- Necessidade de um sistema de alerta para identificar e corrigir problemas de dados antes que eles afetem o sistema.

## Source
https://trello.com/c/M3rAf5tB
