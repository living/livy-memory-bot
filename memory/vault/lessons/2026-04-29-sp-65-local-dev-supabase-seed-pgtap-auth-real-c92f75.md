---
type: lesson
date: 2026-04-29
subject: "Trello: SP 6.5 -  Local Dev Supabase + Seed + pgTAP + Auth Real [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
O objetivo foi substituir o Postgres do docker-compose pelo Supabase CLI local, gerar um seed mascarado de 5.000 registros com tenants reais, cobrir RLS com pgTAP, adicionar suporte a usuários multi-tenant e validar tudo com Playwright autenticado.

## Decisão / Solução
A arquitetura foi definida com o EF Core como fonte de verdade do schema, utilizando `sync-schema.sh` para aplicar SQL idempotente no Supabase CLI. A multi-tenancy foi implementada com uma tabela de junção em vez de uma FK única, e o JWT foi ajustado para carregar um único `tenant_id` por sessão.

## Lessons
- A utilização do Supabase CLI local permite um desenvolvimento mais ágil e controlado, facilitando a integração com a arquitetura existente.
- A abordagem de multi-tenancy com tabela de junção proporciona maior flexibilidade e escalabilidade no gerenciamento de usuários e seus respectivos tenants.

## Source
https://trello.com/c/ejTLFCYb
