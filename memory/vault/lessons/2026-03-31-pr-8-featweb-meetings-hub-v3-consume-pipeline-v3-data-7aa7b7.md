---
type: lesson
subject: "PR #8 — Meetings Hub v3 — consume pipeline v3 data"
author: unknown
tags: [backend, frontend, supabase, testes, arquitetura]
date: 2026-03-31
source: https://github.com/living/livy-tldv-jobs/pull/8

## O que aconteceu
Este PR evolui o pipeline v3 e a interface do web para suportar novas funcionalidades, como memórias de reuniões, listagem de PRs e feedback por insight. Além disso, corrige inconsistências no Supabase e melhora a confiabilidade dos testes.

## Decisão / Solução
Foi decidido criar um cliente Supabase dedicado para memórias, novos endpoints para consultas, e realizar migrações para corrigir colunas e views. O frontend foi atualizado para consumir esses novos dados, melhorando a experiência do usuário e a robustez da aplicação.

## Lessons
- Sempre valide a configuração de variáveis de ambiente críticas para evitar falhas silenciosas em produção.
- Ao introduzir novos tipos de dados, garanta que a tipagem no frontend esteja alinhada com a estrutura real do banco de dados.
- Melhore a visibilidade de erros na UI, utilizando throws em vez de retornar listas vazias, para que os desenvolvedores possam identificar problemas rapidamente.

## Source
https://github.com/living/livy-tldv-jobs/pull/8
