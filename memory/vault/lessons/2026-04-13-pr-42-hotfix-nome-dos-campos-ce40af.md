---
type: lesson
source: github
source_ref: "living/elcano-robo-ocr/pull/42"
date: 2026-04-13
subject: "PR #42 — HotFix nome dos campos"
author: unknown
cycle_time: 3d 16h
tags: [API, JSON, Swagger, Cleanup]

## O que aconteceu
Este PR ajusta a exposição no Swagger e a serialização JSON da aplicação, além de fazer um pequeno cleanup no layout Razor. Controllers de UI/Docs deixam de aparecer na documentação da API, a API passa a usar Newtonsoft.Json com configurações explícitas e o _Layout.cshtml remove duplicidades.

## Decisão / Solução
Foi decidido ocultar controllers não-API do Swagger para manter a documentação mais limpa, além de padronizar a serialização JSON utilizando Newtonsoft.Json. Também foi realizado um cleanup no layout para remover duplicidades.

## Lessons
- Sempre que possível, mantenha a documentação da API focada apenas em endpoints públicos para evitar confusão.
- Ao mudar a serialização JSON, esteja ciente do impacto que isso pode ter nos consumidores da API, especialmente em relação a campos nulos e casing.
- Realizar um cleanup no layout pode melhorar a manutenção do código e a experiência do usuário.

## Source
https://github.com/living/elcano-robo-ocr/pull/42
