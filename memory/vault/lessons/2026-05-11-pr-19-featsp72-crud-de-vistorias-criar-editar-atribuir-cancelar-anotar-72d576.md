---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/19"
date: 2026-05-11
subject: "PR #19 — feat(sp7.2): CRUD de Vistorias — criar, editar, atribuir, cancelar, anotar"
author: unknown
cycle_time: 3d 2h
tags: [CRUD, Vistorias, API, Frontend, Testes]

## O que aconteceu
Este PR implementa um CRUD completo para Vistorias, incluindo a criação, edição, atribuição, cancelamento e anotações, além de listar engenheiros do tenant. Também foi adicionado o campo "Seguradora" na entidade Sinistro, com as devidas migrações e ajustes no frontend e backend.

## Decisão / Solução
Foi decidido implementar novos endpoints para o CRUD de Vistorias, além de atualizar a estrutura do banco de dados para incluir a nova coluna "Seguradora". O frontend foi ajustado para suportar as novas funcionalidades, e testes foram adicionados para garantir a qualidade das implementações.

## Lessons
- Sempre que adicionar novos campos a entidades existentes, planeje e execute migrações adequadas para evitar problemas de compatibilidade.
- A implementação de testes automatizados é crucial para garantir que novas funcionalidades não quebrem o sistema existente.
- Ao modificar contratos de API, comunique claramente as mudanças para todos os consumidores da API para evitar quebras inesperadas.

## Source
https://github.com/living/delphos-svd/pull/19
