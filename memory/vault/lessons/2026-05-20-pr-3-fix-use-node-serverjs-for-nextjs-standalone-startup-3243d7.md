---
type: lesson
source: github
source_ref: "living/insight-funds/pull/3"
date: 2026-05-20
subject: "PR #3 — fix: use node server.js for Next.js standalone startup"
author: unknown
cycle_time: 0m
tags: [Next.js, deployment, server]
---

## O que aconteceu
Este PR ajusta o comando de inicialização do app Next.js (dashboard-ui) para usar um servidor Node customizado. O script `start` foi alterado para executar `node server.js` em vez de `next start -p 3001`.

## Decisão / Solução
A mudança foi feita para alinhar o processo de startup com um fluxo de deploy/execução standalone, onde `server.js` é o entrypoint do runtime, eliminando a dependência do comando `next start`.

## Lessons
- Verifique se o arquivo `server.js` está presente no ambiente de runtime antes de realizar o deploy, pois sua ausência causará falhas na inicialização.
- Confirme que a porta configurada dentro de `server.js` está alinhada com as expectativas dos ambientes de desenvolvimento, homologação e produção.
- Considere a implementação de testes automatizados para validar a presença e a funcionalidade do `server.js` no processo de build.

## Source
https://github.com/living/insight-funds/pull/3
