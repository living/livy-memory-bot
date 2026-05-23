---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/35"
date: 2026-05-22
subject: "PR #35 — fix(svdFetch): crypto.randomUUID falha em HTTP — quebra login no deploy"
author: unknown
cycle_time: 0m
tags: [bugfix, api, segurança]

## O que aconteceu
Este PR corrige a geração do **Idempotency-Key** nas chamadas de API do front-end, substituindo o uso direto de `crypto.randomUUID()` por um gerador compatível com **contextos não seguros (HTTP)**. O motivo da mudança foi que o deploy em **ACI roda em HTTP** e o `crypto.randomUUID()` exige **Secure Context** (HTTPS/localhost), o que estava **quebrando todas as mutações** (POST/PUT/PATCH/DELETE).

## Decisão / Solução
Foi decidido adicionar um fallback para UUIDv4 em `src/SVD.Web/src/lib/svdApi.ts`, que utiliza `crypto.randomUUID()` quando disponível e, caso contrário, gera um UUIDv4 via `crypto.getRandomValues()` ou `Math.random()` como último recurso. O comportamento de geração do **Idempotency-Key** foi mantido, sendo gerado uma vez antes do loop de retry e reaproveitado nas tentativas.

## Lessons
- Sempre considere a compatibilidade do código com ambientes que não suportam Secure Context, especialmente ao lidar com identificadores únicos.
- A implementação de fallbacks deve ser feita com cuidado, garantindo que a segurança não seja comprometida, mesmo que a funcionalidade seja mantida.
- Testes em diferentes ambientes (HTTP/HTTPS) são essenciais para garantir que o sistema funcione corretamente em todas as condições de uso.

## Source
https://github.com/living/delphos-svd/pull/35
