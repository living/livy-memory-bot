---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/23"
date: 2026-05-15
subject: "PR #23 — feat(SP7.3): pós-demo quick wins + simulador SINDelphos"
author: unknown
cycle_time: 2h 27m
tags: [feature, improvement, security, testing, UX]

## O que aconteceu
Este PR implementa a SP7.3, que introduz um fluxo completo de simulação para criação de vistorias e atribuição de engenheiro, com novos endpoints na API, uma nova página no frontend, e melhorias em segurança e formatação de datas.

## Decisão / Solução
Foi decidido criar um simulador para facilitar a realização de demos, implementando proteções como rate limiting e feature flags. Além disso, foram feitas melhorias na privacidade dos dados e na experiência do usuário na interface web.

## Lessons
- Implementar rate limiting em endpoints sensíveis é crucial para evitar abusos e garantir a segurança da aplicação.
- A padronização de datas em UTC ajuda a evitar problemas relacionados a fusos horários e facilita a integração com sistemas externos.
- Remover informações pessoais sensíveis de logs é uma prática essencial para proteger a privacidade dos usuários e evitar vazamentos de dados.

## Source
https://github.com/living/delphos-svd/pull/23
