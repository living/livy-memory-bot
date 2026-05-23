---
type: lesson
source: github
source_ref: "living/bot-ai-api/pull/129"
date: 2026-05-21
subject: "PR #129 — correcao contatos"
author: unknown
cycle_time: 0m
tags: [bugfix, refactor, database]

## O que aconteceu
Foi realizado um ajuste no fluxo de criação e atualização de contatos no Supabase para evitar erros de duplicidade e tornar o comportamento idempotente. Agora, ao detectar um contato existente, o sistema reaproveita o registro e executa um UPDATE, caso contrário, realiza um INSERT.

## Decisão / Solução
A lógica que lidava com duplicidade de contatos foi normalizada. A busca inicial foi simplificada e agora utiliza `cpf_cnpj` para comparação. O uso de upsert foi substituído por UPDATE e INSERT, o que altera o comportamento em cenários de conflito de chave única.

## Lessons
- Sempre valide as mudanças nos critérios de busca para evitar correspondências incorretas.
- Considere as implicações de substituir upsert por UPDATE/INSERT, especialmente em relação a constraints no banco de dados.
- Mantenha a validação de campos obrigatórios, mesmo após alterações na lógica de inserção/atualização.

## Source
https://github.com/living/bot-ai-api/pull/129
