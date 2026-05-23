---
type: lesson
source: github
source_ref: "living/fs-memory/pull/8"
date: 2026-04-09
subject: "PR #8 — feat: Add speaker diarization with Pyannote.audio"
author: unknown
cycle_time: 1d 0h
tags: [diarização, Pyannote, transcrição, melhorias]

## O que aconteceu
Este PR melhora e amplia o suporte a **speaker diarization** no pipeline de vídeo. Inclui um novo plugin baseado em **Pyannote.audio**, ajusta a lógica de merge entre transcrição e diarização para ser **mais justa (normalizada pela duração do segmento)** e adiciona **fallback resiliente**: se a diarização falhar, a transcrição continua sendo entregue (sem speakers). Também atualiza dependências e adiciona testes cobrindo os novos cenários.

## Decisão / Solução
Foi decidido implementar um novo plugin de diarização utilizando a biblioteca **Pyannote.audio**, que permite uma melhor atribuição de falas aos speakers. A lógica de merge foi ajustada para priorizar a fração de overlap em vez do tempo absoluto, evitando que segmentos longos ganhem injustamente. Além disso, foi implementado um sistema de fallback que garante a entrega da transcrição mesmo em caso de falha na diarização.

## Lessons
- Sempre que implementar novas funcionalidades, considere a possibilidade de um fallback para garantir a continuidade do serviço.
- Ao realizar merges de dados, priorize métricas que representem melhor a realidade do problema, como a fração de overlap, em vez de contagens absolutas.
- A documentação e os testes são essenciais para garantir que novas dependências e funcionalidades sejam integradas sem problemas no pipeline existente.

## Source
https://github.com/living/fs-memory/pull/8
