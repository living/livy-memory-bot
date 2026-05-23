---
type: lesson
subject: "PR #90 — mais informações na tela do google drive"
author: unknown
date: 2026-05-08
cycle_time: 15h 54m
tags: [segurança, UX, Google Drive]

## O que aconteceu
Este PR introduziu melhorias de segurança e experiência do usuário (UX) em duas áreas principais: a abertura de links externos no Chatboard Panel e a exibição de estatísticas de pastas no Google Drive.

## Decisão / Solução
Foi decidido adicionar a biblioteca `markdown-it-external-links` para garantir que links externos abram em uma nova aba com segurança, evitando riscos de `window.opener`. Além disso, foram implementadas melhorias na interface do Google Drive para mostrar estatísticas da pasta atual, facilitando a visualização do conteúdo sem a necessidade de abrir cada item.

## Lessons
- Sempre que adicionar links externos, utilize `target="_blank"` junto com `rel="noopener noreferrer"` para aumentar a segurança e melhorar a experiência do usuário.
- Ao implementar novas funcionalidades que dependem de dados do backend, assegure-se de que o formato do payload esteja alinhado com as expectativas do frontend para evitar erros de compatibilidade.
- Considere a performance da aplicação ao adicionar novas requisições, como a chamada de `getFolderStats`, e avalie o impacto na experiência do usuário.

## Source
https://github.com/living/bot-ai-app/pull/90
