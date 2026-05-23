---
type: lesson
source: github
source_ref: "living/bot-ai-api/pull/119"
date: 2026-05-08
subject: "PR #119 — mais informações na tela do google drive"
author: unknown
cycle_time: 15h 51m
tags: [webchat, segurança, API, refatoração]

## O que aconteceu
Este PR introduziu melhorias significativas no Webchat, incluindo a renderização e segurança de links via Markdown, além de expandir as capacidades do Google Drive com um novo endpoint de estatísticas de pasta. Também houve uma grande limpeza de código, removendo serviços legados de importação, indicando uma migração de responsabilidade para outra camada.

## Decisão / Solução
Foi decidido refatorar o código do Webchat para garantir uma melhor segurança e experiência do usuário ao lidar com links. Além disso, a implementação de um novo endpoint para métricas de pasta foi realizada, enquanto serviços legados foram removidos para reduzir o acoplamento e facilitar a manutenção.

## Lessons
- Sempre que implementar links externos, utilize `rel="noopener noreferrer"` para mitigar riscos de segurança.
- A remoção de código legado deve ser feita com cautela, garantindo que não haja dependências não resolvidas que possam quebrar funcionalidades existentes.
- Testes rigorosos são essenciais após grandes refatorações para garantir que novas implementações não introduzam regressões.

## Source
https://github.com/living/bot-ai-api/pull/119
