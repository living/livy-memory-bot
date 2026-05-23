---
type: lesson
date: 2026-05-11
subject: "Trello: Novo Query Unsafe [B3/Balcão]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3balco]
---

## O que aconteceu
Foi identificado a necessidade de melhorias na área de digitação da query no sistema de Query Unsafe.

## Decisão / Solução
As melhorias propostas incluem: 
- Implementação de um componente que reconheça a query digitada, sem realizar verificação ortográfica.
- Limpeza dos resultados ao clicar em "executar" e registro da data/hora de início da execução.
- Implementação de log para registrar o usuário autenticado, a máquina utilizada e a query executada.

## Lessons
- A interface do usuário deve ser intuitiva e facilitar a entrada de dados sem interferências desnecessárias.
- A documentação e o registro de atividades são cruciais para auditoria e rastreamento de ações no sistema.

## Source
https://trello.com/c/Tu3spkat
