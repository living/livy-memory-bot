---
type: lesson
source: github
source_ref: "living/bot-ai-app/pull/93"
date: 2026-05-08
subject: "PR #93 — correcao salvar como"
author: unknown
cycle_time: 0m
tags: [UI, usabilidade, manutenção]

## O que aconteceu
Este PR realiza um ajuste na interface do **Chatboard Panel**, removendo a opção **“Salvar como...”** para mensagens do tipo **documento/anexo**. A mudança foi feita para evitar confusões e problemas de usabilidade.

## Decisão / Solução
A decisão foi comentar o botão **“Salvar como...”** no HTML, mantendo apenas a opção **“Abrir”** disponível. Essa abordagem foi escolhida por ser rápida e pouco invasiva, embora possa resultar em código não utilizado no futuro.

## Lessons
- Evitar comentar código em vez de removê-lo completamente, para prevenir confusões futuras na manutenção.
- Sempre considerar a experiência do usuário ao desabilitar funcionalidades, garantindo que a interface permaneça intuitiva.
- Testar as mudanças em diferentes navegadores para assegurar que a usabilidade e a aparência da interface sejam consistentes.

## Source
https://github.com/living/bot-ai-app/pull/93
