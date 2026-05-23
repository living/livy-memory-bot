---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/34"
date: 2026-05-22
subject: "PR #34 — feat(SP8-A): Gestão de Engenheiros — migrate, login, CRUD, presença"
author: unknown
cycle_time: 8h 33m
tags: [gestão, migração, autenticação, CRUD, presença]

## O que aconteceu
Este PR entrega a feature **Gestão de Engenheiros** de ponta a ponta, incluindo migração de dados legados, um novo fluxo de autenticação, CRUD completo de engenheiros e um mecanismo de presença.

## Decisão / Solução
Foi decidido implementar uma migração de dados legados para um novo modelo, além de criar um fluxo de autenticação que reduz o atrito no login. O CRUD de engenheiros foi desenvolvido com controle de acesso via RBAC, e um sistema de presença foi adicionado para monitorar o status online dos engenheiros.

## Lessons
- Sempre validar a idempotência de operações críticas, como migrações de dados, para evitar duplicações ou perdas de informações.
- Implementar medidas de segurança, como rate limiting e respostas consistentes, para mitigar riscos de enumeração de usuários em fluxos de autenticação.
- Realizar testes manuais e automatizados abrangentes após grandes alterações, especialmente em funcionalidades críticas como login e gestão de usuários.

## Source
https://github.com/living/delphos-svd/pull/34
