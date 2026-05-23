---
type: lesson
source: github
source_ref: "living/dashvoice/pull/11"
date: 2026-04-09
subject: "PR #11 — correcao autenticacao microsoft"
author: unknown
cycle_time: 0m
tags: [auth, frontend, angular]

## O que aconteceu
Este PR faz um ajuste na chave usada no `localStorage` para identificar autenticação via Microsoft no frontend (Angular). A chave foi padronizada de `microsoftAuthenticated` para `microsoftAuth`, garantindo consistência na leitura e remoção desse estado durante o logout e na checagem de sessão.

## Decisão / Solução
A decisão foi padronizar o nome da flag de autenticação Microsoft armazenada no navegador para evitar inconsistências entre o valor setado e o valor removido/lido no `AuthService`. A mudança garante que o logout limpe corretamente a nova chave e que a autenticação seja verificada de forma consistente.

## Lessons
- Padronizar nomes de variáveis e chaves no armazenamento local é crucial para evitar inconsistências no estado da aplicação.
- Sempre considerar o impacto de mudanças em chaves de autenticação, especialmente para usuários já logados.
- Implementar um fallback temporário pode ser uma boa prática para garantir a compatibilidade com versões anteriores.

## Source
https://github.com/living/dashvoice/pull/11
