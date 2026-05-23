---
type: lesson
date: 2023-10-13
subject: "Trello: SP 5.5 Hydra HTTP + Demo de Agendamento [Delphos/SVD]"
effort: Not specified
pr_refs: [none]
tags: [trello, delphossvd]
---

## O que aconteceu
Foi realizada uma demonstração do agendamento via Hydra, utilizando o SVD e o plugin Delphos Connect. A configuração e os passos necessários para a execução do agendamento foram detalhados.

## Decisão / Solução
A solução para o agendamento foi implementada utilizando um fluxo que envolve a criação de uma vistoria, a proposta de datas via API, e a confirmação do agendamento através do WhatsApp. Foram estabelecidos pré-requisitos e um cenário de happy path para garantir que o processo funcione corretamente.

## Lessons
- A integração entre o SVD e o Hydra requer uma configuração cuidadosa dos webhooks e tokens para garantir a comunicação adequada entre os sistemas.
- A validação de cada etapa do processo é crucial para identificar rapidamente problemas, como falhas de autenticação ou webhooks não recebidos.

## Source
https://trello.com/c/6ScckyZe
