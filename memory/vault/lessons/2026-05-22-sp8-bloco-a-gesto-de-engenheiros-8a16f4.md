---
type: lesson
date: 2026-05-22
subject: "Trello: SP8 Bloco A — Gestão de Engenheiros [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
O cartão representa a migração de engenheiros dos backups SVR+SOR para as tabelas `svd.usuarios` e `svd.usuario_tenants`, além da implementação do primeiro login via magic link lazy utilizando Supabase Auth e a entrega da página `/engenheiros` com funcionalidades de CRUD, atribuição por tenant e presença online.

## Decisão / Solução
A solução envolve a criação de uma CLI standalone para a migração, utilizando o padrão `MaskingExtractor`. O provisionamento lazy permite que os usuários comecem com `AuthId=NULL`, recebendo uma linha em `auth.users` somente no primeiro login. A presença online é gerenciada através de um heartbeat throttled, utilizando um middleware fire-and-forget e um BackgroundService para atualizações em lote.

## Lessons
- A migração de dados deve ser planejada com uma arquitetura que suporte provisionamento lazy, garantindo que os usuários sejam criados apenas quando necessário.
- A implementação de um sistema de presença online deve considerar a eficiência e a escalabilidade, utilizando técnicas como throttling e processamento em segundo plano.

## Source
https://trello.com/c/1mmWDqBk
