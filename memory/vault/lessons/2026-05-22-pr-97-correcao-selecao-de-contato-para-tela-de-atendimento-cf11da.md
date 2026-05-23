---
type: lesson
source: github
source_ref: "living/bot-ai-app/pull/97"
date: 2026-05-22
subject: "PR #97 — correcao selecao de contato para tela de atendimento"
author: unknown
cycle_time: 0m
tags: [bugfix, UI, refactor]

## O que aconteceu
Este PR corrige o comportamento de seleção de contato na tela de atendimento e faz ajustes de UI/markup em telas relacionadas. Também foram realizados ajustes no fluxo de carregamento da lista de mensagens para evitar inconsistências ao selecionar um atendimento.

## Decisão / Solução
Foi decidido que o `PanelComponent` não deve mais resetar a `messageList` durante a seleção de contatos, e o `PanelService` deve sempre ordenar e atualizar a lista de mensagens, mesmo quando a API retorna uma lista vazia. Além disso, houve uma mudança de terminologia na UI de "Departamento" para "Condomínio".

## Lessons
- Sempre garantir que a lista de mensagens seja atualizada, mesmo quando a API retorna uma lista vazia, para evitar inconsistências na UI.
- Mudanças de terminologia na UI devem ser cuidadosamente avaliadas para garantir que não causem confusão entre os usuários.
- Refatorações de código que melhoram a legibilidade e a manutenção futura são importantes, mesmo que não resultem em mudanças funcionais imediatas.

## Source
https://github.com/living/bot-ai-app/pull/97
