---
type: lesson
source: github
source_ref: "living/delphos-svd/issues/41"
date: 2026-05-26
subject: "Issue #41 — [SP8-A] POST /api/engenheiros: validação cross-tenant não impede criação em tenant que admin não pertence"
author: unknown
cycle_time: N/A
tags: [bug, segurança, validação]
---

## O que aconteceu
O endpoint `POST /api/engenheiros` apresentou um problema de validação que permitia que um administrador criasse engenheiros vinculados a tenants dos quais ele não fazia parte. Isso representa um risco de segurança, pois deveria retornar um erro 400.

## Decisão / Solução
Foi decidido adicionar uma validação no endpoint para garantir que o administrador tenha vínculo com pelo menos um dos tenants solicitados antes de permitir a criação do engenheiro. Além disso, o sistema deve retornar um erro 400 com uma mensagem clara se essa condição não for atendida.

## Lessons
- Sempre valide o escopo de acesso em operações sensíveis, como a criação de recursos, para evitar falhas de segurança.
- Mensagens de erro claras são essenciais para facilitar a identificação de problemas durante o desenvolvimento e testes.
- Testes automatizados devem cobrir cenários de validação de acesso para garantir que mudanças futuras não introduzam regressões.

## Source
https://github.com/living/delphos-svd/issues/41
