---
type: lesson
source: trello
source_ref: "trello/6a0f015b71dc7d38e0c4fd55"
date: 2026-05-21
subject: "Trello: [TAR-11441] Correção CNPJ alfanumérico na exportação de clientes do SAP [B3/UIF+NW+NT]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3uifnwnt]
---

## O que aconteceu
O CNPJ alfanumérico no layout de clientes do SAP estava sendo exportado apenas com números, o que não atende aos requisitos de formatação.

## Decisão / Solução
Foi decidido implementar uma correção para garantir que o CNPJ seja exportado corretamente, mantendo o formato alfanumérico necessário.

## Lessons
- A validação de dados deve ser uma prioridade na exportação para evitar problemas de formatação.
- Revisar e testar os layouts de exportação regularmente pode prevenir falhas semelhantes no futuro.

## Source
https://trello.com/c/E6yIOBlW
