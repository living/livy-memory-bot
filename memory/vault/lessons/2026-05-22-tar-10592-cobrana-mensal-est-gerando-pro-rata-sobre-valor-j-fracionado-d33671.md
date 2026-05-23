---
type: lesson
date: 2026-05-22
subject: "Trello: [TAR-10592] Cobrança mensal está gerando pro-rata sobre valor já fracionado [B3/Listados]"
effort: Not specified
pr_refs: [none]
tags: [trello, b3listados]
---

## O que aconteceu
A cobrança mensal está gerando um cálculo pro-rata sobre valores que já foram fracionados anteriormente, especialmente quando há isenção na mensalidade.

## Decisão / Solução
Foi identificado que a tarifação do primeiro nível, ao gerar um pro-rata, não deve ser recalculada caso haja isenção, para evitar duplicidade nos cálculos.

## Lessons
- É crucial revisar os cálculos de tarifação para evitar erros de pro-rata em casos de isenção.
- A implementação de regras claras para a tarifação pode prevenir confusões e garantir a precisão nas cobranças.

## Source
https://trello.com/c/JH9aoP5i
