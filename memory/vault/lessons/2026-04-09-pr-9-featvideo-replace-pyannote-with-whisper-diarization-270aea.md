---
type: lesson
subject: "PR #9 — feat(video): replace Pyannote with whisper-diarization"
author: unknown
cycle_time: 41m
tags: [diarização, transcrição, plugin]
date: 2026-04-09

## O que aconteceu
Este PR introduziu a funcionalidade de **speaker diarization** ao pipeline de vídeo/transcrição, utilizando o projeto **whisper-diarization**. A implementação inclui uma nova interface de plugin, um algoritmo de merge temporal para atribuição de falantes e uma suíte de testes abrangente.

## Decisão / Solução
Foi decidido implementar um novo plugin de diarização que chama um subprocesso do whisper-diarization. A integração com o plugin de transcrição existente foi feita para permitir a atribuição de falantes aos segmentos transcritos, utilizando uma estratégia de merge baseada em sobreposição temporal.

## Lessons
- A documentação do projeto deve ser cuidadosamente gerida para evitar substituições indesejadas, como a troca do README.md que pode impactar a apresentação do projeto.
- Dependências pesadas devem ser avaliadas quanto ao impacto no CI/CD, considerando alternativas como a abordagem "vendorizada" para evitar conflitos.
- A estratégia de merge por overlap temporal, embora simples, pode falhar em cenários específicos, como falas curtas ou cortes desalinhados, e deve ser testada em diferentes condições.

## Source
https://github.com/living/fs-memory/pull/9
