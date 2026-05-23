---
type: lesson
source: github
source_ref: "living/elcano-robo-ocr/pull/41"
date: 2026-04-09
subject: "PR #41 — Corrige nomes dos campos JSON para compatibilidade com versão anterior"
author: unknown
cycle_time: 55m
tags: [json, aspnetcore, compatibilidade]

## O que aconteceu
Este PR adiciona suporte explícito ao Newtonsoft.Json na pipeline de controllers do ASP.NET Core, configurando o serializer para camelCase, ignorar loops de referência e valores nulos. O objetivo é manter a compatibilidade com versões anteriores e garantir que atributos como [JsonProperty] sejam respeitados na serialização JSON.

## Decisão / Solução
Foi decidido adicionar a configuração `.AddNewtonsoftJson(...)` para garantir o uso do Newtonsoft.Json, evitando que endpoints que dependem de anotações Newtonsoft quebrem. Além disso, foram implementadas configurações para padronizar a serialização e evitar exceções em casos de referências circulares.

## Lessons
- Sempre que houver dependências de serialização específicas, configure explicitamente o serializer para evitar quebras em endpoints.
- Considere o impacto de mudanças na serialização, como a omissão de campos nulos, que pode afetar consumidores de APIs.
- Valide contratos antigos ao introduzir alterações na serialização para garantir que não haja regressões.

## Source
https://github.com/living/elcano-robo-ocr/pull/41
