---
type: lesson
source: github
source_ref: "living/delphos-svd/pull/8"
date: 2026-04-20
subject: "PR #8 — feat(sp4): Video Vonage — sessão, tokens, archive, PWA VideoCall"
author: unknown
cycle_time: 2d 18h
tags: [video, integration, backend, frontend, testing]

## O que aconteceu
Este PR implementa a integração de vídeo com Vonage no SVD, adicionando uma base completa para chamadas de vídeo, controle de gravação e preparação de webhook. O objetivo é habilitar a vistoria por vídeo, reduzindo custos e aumentando a rastreabilidade.

## Decisão / Solução
Foi decidido consolidar um fluxo end-to-end para a criação de sessões Vonage automaticamente durante a vistoria, além de implementar novos endpoints REST e preparar a infraestrutura para futuras transcrições de áudio.

## Lessons
- Sempre valide a consistência dos eventos publicados em relação às transações para evitar inconsistências no sistema.
- Documente as mudanças na API e as recomendações de uso de mocks para facilitar a integração e testes futuros.
- Ao implementar novas funcionalidades, considere a segurança e a autorização, garantindo que os endpoints estejam protegidos adequadamente.

## Source
https://github.com/living/delphos-svd/pull/8
