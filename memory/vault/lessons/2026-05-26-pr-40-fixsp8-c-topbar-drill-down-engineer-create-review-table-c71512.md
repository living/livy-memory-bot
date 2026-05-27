---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/40"
date: 2026-05-26
subject: "PR #40 — Correção na Topbar e Fluxo de Criação de Engenheiros"
author: unknown
cycle_time: 1h 56m
tags: [UI, Backend, Testes]

## O que aconteceu
Este PR é um follow-up pós-merge do SP8 e foca em corrigir lacunas operacionais e finalizar a experiência de UI do Hydra Event Feed, além de conectar o fluxo de criação de engenheiros no front. As principais entregas incluem a implementação de paginação via `offset` na API, um widget HydraFeed redesenhado, uma nova página de eventos com drill-down por correlação, e a funcionalidade do botão "Adicionar engenheiro".

## Decisão / Solução
Foi decidido implementar a paginação no endpoint de eventos do Hydra para melhorar a escalabilidade e a navegação. Além disso, o fluxo de criação de engenheiros foi integrado à UI, permitindo que o frontend chamasse o endpoint correspondente. Testes de integração foram adicionados para garantir a funcionalidade do novo fluxo.

## Lessons
- A implementação de paginação via `offset` no backend é crucial para suportar um frontend responsivo e escalável.
- A navegação dedicada para drill-down melhora a experiência do usuário, mas aumenta a complexidade do gerenciamento de rotas.
- A adição de testes de integração é essencial para garantir a confiabilidade do novo fluxo de criação de engenheiros e evitar regressões.

## Source
https://github.com/living/delphos-svd/pull/40
