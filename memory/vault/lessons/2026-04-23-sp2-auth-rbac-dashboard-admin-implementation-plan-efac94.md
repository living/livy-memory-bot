---
type: lesson
date: 2026-04-23
subject: "Trello: SP2 — Auth & RBAC + Dashboard Admin: Implementation Plan [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
Este cartão representa o plano de implementação para autenticação e controle de acesso baseado em função (RBAC) utilizando Supabase Auth com JWT, definindo três perfis de usuário e um dashboard restrito.

## Decisão / Solução
A arquitetura proposta utiliza JWT Bearer para validação de tokens, com middleware que extrai informações do token para configurar o serviço de tenant atual. A autorização é baseada em políticas que consideram o perfil do usuário, garantindo que o acesso ao dashboard seja restrito ao perfil adequado.

## Lessons
- A implementação de um middleware para gerenciar o tenant atual é crucial para o isolamento multi-tenant e a segurança da aplicação.
- A utilização de políticas de autorização baseadas em claims permite uma gestão flexível e escalável dos perfis de usuário.

## Source
https://trello.com/c/4JV2wVCg
