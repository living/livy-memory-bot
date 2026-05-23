---
type: lesson
subject: "PR #14 — feat(vault-insights): ativa envio real do resumo semanal"
author: unknown
cycle_time: 0m
tags: [atualização, Telegram, automação]
---

## O que aconteceu
Este PR atualiza o script `vault/insights/envia_resumo.py` para enviar o `resumo-semanal.md` de verdade para o Telegram via Telegram Bot API, implementando controle de deduplicação semanal e suporte a configuração por variáveis de ambiente.

## Decisão / Solução
A decisão foi implementar o envio real das mensagens para o Telegram, utilizando a API de Bot do Telegram e garantindo que o envio não ocorra mais de uma vez por semana. O script agora suporta variáveis de ambiente para configuração e um modo dry-run para testes.

## Lessons
- Sempre que implementar uma nova funcionalidade que depende de configurações externas, considere a utilização de variáveis de ambiente para facilitar a configuração em diferentes ambientes.
- Ao adicionar funcionalidades que alteram o comportamento do sistema, como o envio de mensagens, é crucial documentar claramente as mudanças para evitar confusões futuras.
- Testes abrangentes são essenciais para validar novas funcionalidades, especialmente quando envolvem interações com APIs externas, como a do Telegram.

## Source
https://github.com/living/livy-memory-bot/pull/14
