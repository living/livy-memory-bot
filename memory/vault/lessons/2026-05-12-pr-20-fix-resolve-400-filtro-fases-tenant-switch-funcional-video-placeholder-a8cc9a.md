---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/20"
date: 2026-05-12
subject: "PR #20 — Correção de filtro de fases e melhorias de multi-tenant"
author: unknown
cycle_time: 3h 13m
tags: [bugfix, multi-tenant, experiência do usuário]

## O que aconteceu
Este PR entregou um conjunto de correções e melhorias na experiência do usuário, focando em multi-tenant, filtro por fase e acesso a vídeo. As principais mudanças incluem a correção de um erro 400 no filtro de fases, a implementação de um sistema de troca de tenant para administradores e a adição de uma rota dedicada para vídeos.

## Decisão / Solução
Foi decidido criar uma fonte canônica para mapear os valores de fase do frontend para os esperados pelo backend, além de implementar um sistema que permite aos administradores trocar de tenant sem comprometer a segurança. Também foi criada uma rota específica para vídeos, melhorando a navegação e a experiência do usuário.

## Lessons
- A implementação de uma fonte canônica para valores de fase pode evitar erros de tradução entre frontend e backend, melhorando a robustez da aplicação.
- A validação de acesso através de headers para troca de tenant é uma solução eficaz para manter a segurança em ambientes multi-tenant.
- Criar rotas dedicadas para funcionalidades específicas, como vídeos, pode melhorar a experiência do usuário e a organização do código.

## Source
https://github.com/living/delphos-svd/pull/20
