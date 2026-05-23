---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/12"
date: 2026-04-23
subject: "PR #12 — feat(sp6): Web Shell + Design System + Auth"
author: unknown
cycle_time: 1h 32m
tags: [CORS, React, TypeScript, Supabase, TailwindCSS]

## O que aconteceu
Este PR introduz a configuração de CORS na API (.NET) e adiciona um novo frontend web em React + TypeScript + Vite, com autenticação via Supabase, rotas protegidas e um layout base. O objetivo principal é viabilizar o consumo da API por staging/mobile e iniciar a camada web do SVD.

## Decisão / Solução
Foi decidido habilitar CORS na API para permitir acesso do frontend e criar um novo projeto web com estrutura inicial, autenticação e um design system utilizando TailwindCSS. A integração de desenvolvimento via proxy foi configurada para evitar problemas de CORS durante o desenvolvimento.

## Lessons
- Sempre verifique as configurações de CORS para cada ambiente, garantindo que `Cors:AllowedOrigins` esteja corretamente definido.
- Considere a possibilidade de precisar de cookies ou credenciais em futuras implementações e ajuste a política de CORS conforme necessário.
- Mantenha a documentação atualizada, especialmente em relação às variáveis de ambiente necessárias para o funcionamento do sistema.

## Source
https://github.com/living/delphos-svd/pull/12
