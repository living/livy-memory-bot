---
type: lesson
source: github
source_ref: "living/bot-ai-api/pull/131"
date: 2026-05-22
subject: "PR #131 — correcao contatos"
author: unknown
cycle_time: 0m
tags: [bugfix, performance, database]

## O que aconteceu
Este PR ajusta a rotina de persistência e busca de contatos no Supabase para evitar consultas desnecessárias quando não há identificadores, mudar o critério de busca para usar `id` em vez de `cpf_cnpj`, e garantir que o retorno de dados no insert seja feito corretamente.

## Decisão / Solução
Foi decidido que a busca por contatos existentes deve ser condicional, utilizando apenas `id` ou `idContato`. Além disso, o insert foi modificado para retornar dados, e um log de diagnóstico foi adicionado para casos em que o insert não retorna dados, ajudando na identificação de problemas.

## Lessons
- Sempre verifique se os identificadores utilizados nas consultas estão alinhados com os dados que representam para evitar inconsistências.
- Adicione logs de diagnóstico em operações críticas para facilitar a identificação de problemas em produção.
- Considere o impacto de mudanças semânticas nas consultas, especialmente em relação à deduplicação de registros.

## Source
https://github.com/living/bot-ai-api/pull/131
