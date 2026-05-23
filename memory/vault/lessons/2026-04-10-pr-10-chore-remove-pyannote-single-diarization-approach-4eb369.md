---
type: lesson
subject: "PR #10 — Remoção do Pyannote"
author: unknown
date: 2026-04-10
cycle_time: 14m
tags: [chore, diarization, refactor]
---

## O que aconteceu
Este PR remove completamente o plugin de diarização baseado em **Pyannote** e sua dependência `pyannote-audio`, incluindo código, testes e entradas de lockfile. A mudança foi feita para desacoplar o projeto de `pyannote-audio` e consolidar a estratégia de diarização em torno do plugin alternativo **WhisperDiarizationPlugin**.

## Decisão / Solução
A decisão foi remover o plugin Pyannote e todos os seus testes, além de ajustar as dependências para garantir que o projeto não dependesse mais de `pyannote-audio`. Foram adicionados testes para assegurar que o novo plugin de diarização está disponível e funcionando corretamente.

## Lessons
- Remover dependências desnecessárias pode simplificar o projeto e reduzir a complexidade do lockfile.
- É importante garantir que a remoção de um plugin não quebre a funcionalidade existente, verificando referências e configurações.
- Testes devem ser adaptados para garantir a funcionalidade do novo plugin e cobrir cenários críticos que antes eram garantidos pelo plugin removido.

## Source
https://github.com/living/fs-memory/pull/10
