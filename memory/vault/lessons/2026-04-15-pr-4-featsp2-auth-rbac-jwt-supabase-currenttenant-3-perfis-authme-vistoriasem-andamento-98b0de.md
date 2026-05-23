---
type: lesson
subject: "PR #4 — feat(sp2): Auth & RBAC — JWT Supabase, CurrentTenant, 3 perfis, /auth/me, /vistorias/em-andamento"
author: unknown
cycle_time: 36m
tags: [auth, rbac, jwt, multi-tenancy, api]
date: 2026-04-15

## O que aconteceu
Este PR introduziu autenticação JWT utilizando Supabase na API, implementou multi-tenancy e adicionou endpoints protegidos. Também foram feitas melhorias na documentação e ajustes em arquivos auxiliares.

## Decisão / Solução
Foi decidido implementar autenticação via JWT com validação de claims para controle de acesso, além de configurar middleware para resolver o tenant atual baseado no usuário autenticado. Novos serviços e políticas foram criados para suportar a nova arquitetura.

## Lessons
- A configuração obrigatória do `Supabase:JwtSecret` melhora a segurança, mas pode impactar a experiência do desenvolvedor e a integração contínua, exigindo que todos os ambientes estejam configurados corretamente.
- A resolução de tenant no middleware depende da existência do usuário no banco de dados, o que pode levar a falhas de autorização se o usuário não estiver provisionado.
- A separação de enums no schema `public` e tabelas no schema `svd` deve ser mantida para evitar problemas de consistência em tempo de execução.

## Source
https://github.com/living/delphos-svd/pull/4
