---
type: lesson
date: 2026-04-28
subject: "Trello: Subir erro de indisponibilidade do SAP mais legivel [CERC/Billing]"
effort: Not specified
pr_refs: [none]
tags: [trello, cercbilling]
---

## O que aconteceu
Foi identificado que, quando o endpoint está disponível, o POST da API de autenticação retorna um erro 503 com HTML que contém detalhes da indisponibilidade. No entanto, esse erro não é registrado de forma legível no log ou no retorno da execução, dificultando a compreensão do usuário sobre o que está ocorrendo.

## Decisão / Solução
Decidiu-se que o erro 503 deve ser tratado e retornado de maneira legível para a execução do adapter, garantindo que os usuários possam entender a situação de indisponibilidade.

## Lessons
- A importância de registrar erros de forma legível para facilitar a identificação e resolução de problemas.
- Necessidade de melhorar a comunicação de falhas para os usuários finais, evitando confusões e aumentando a eficiência na resolução de problemas.

## Source
https://trello.com/c/OulUWRlY
