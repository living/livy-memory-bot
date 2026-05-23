---
type: lesson
source: github
source_ref: "living/livy-memory-bot/pull/15"
date: 2026-04-18
subject: "PR #15 — fix(vault-insights): fallback para TELEGRAM_TOKEN no envia_resumo"
author: unknown
cycle_time: 0m
tags: [bot, telegram, configuração]

## O que aconteceu
Este PR ajusta a configuração do bot de Telegram no módulo de envio de resumo, passando a aceitar duas variáveis de ambiente como fonte do token: `TELEGRAM_BOT_TOKEN` (preferencial) e, como fallback, `TELEGRAM_TOKEN`. O objetivo é evitar falhas de envio quando o ambiente/CI usa nomenclatura diferente para o token.

## Decisão / Solução
Foi implementado um fallback para a variável de ambiente do token do Telegram, permitindo que o sistema funcione com setups antigos ou alternativos. A precedência entre as variáveis foi definida, garantindo que `TELEGRAM_BOT_TOKEN` tenha prioridade sobre `TELEGRAM_TOKEN`.

## Lessons
- Sempre que possível, implemente fallbacks em configurações críticas para aumentar a robustez do sistema.
- Documente claramente a precedência de variáveis de ambiente para evitar confusões futuras.
- Considere adicionar logs ou mensagens de erro explícitas quando variáveis essenciais não estiverem configuradas.

## Source
https://github.com/living/livy-memory-bot/pull/15
