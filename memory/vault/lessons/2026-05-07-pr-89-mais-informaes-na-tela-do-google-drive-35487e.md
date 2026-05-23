---
type: lesson
source: github
source_ref: "living/bot-ai-app/pull/89"
date: 2026-05-07
subject: "PR #89 — mais informações na tela do google drive"
author: unknown
cycle_time: 0m
tags: [UX, segurança, Google Drive]

## O que aconteceu
Este PR introduziu melhorias de experiência do usuário (UX) e segurança em duas áreas principais: o Chatboard e o Google Drive Provider. No Chatboard, links renderizados via Markdown agora são tratados como links externos seguros, enquanto no Google Drive Provider, foram adicionadas estatísticas da pasta e metadados dos arquivos.

## Decisão / Solução
Foi decidido adicionar a dependência `markdown-it-external-links` para garantir que os links no Chatboard abram em uma nova aba e tenham proteção contra tabnabbing. Além disso, um painel de estatísticas foi implementado no Google Drive Provider para fornecer informações sobre a pasta selecionada, como a quantidade de arquivos e o tamanho total.

## Lessons
- Sempre que adicionar links externos, considere implementar medidas de segurança como `rel="noopener noreferrer"` para evitar vulnerabilidades de tabnabbing.
- Melhorar a UX com informações contextuais, como estatísticas e metadados, pode ajudar os usuários a tomar decisões mais informadas rapidamente.
- Testes rigorosos são essenciais para validar novas funcionalidades, especialmente quando envolvem mudanças na renderização e chamadas de API.

## Source
https://github.com/living/bot-ai-app/pull/89
