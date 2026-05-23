---
type: lesson
date: 2026-04-02
subject: "PR #11 — Remoção de painéis inativos e melhoria na transcrição"
author: unknown
tags: [frontend, transcrição, melhorias]

## O que aconteceu
Este PR introduziu melhorias significativas na etapa de transcrição e enriquecimento, priorizando a API do tl;dv para obter labels de oradores e integrando com o Whisper para uma transcrição mais precisa. Além disso, o formato de `insights_json` foi padronizado para o frontend, e seções antigas de Trello e GitHub foram removidas da interface.

## Decisão / Solução
A decisão foi mudar a ordem de uso das APIs, utilizando primeiro a do tl;dv e, em caso de necessidade, o Whisper como complemento. O backend agora escreve `insights_json` em um formato que o frontend pode consumir diretamente, simplificando a interface do usuário ao eliminar seções que não eram mais relevantes.

## Lessons
- Priorizar a API que fornece informações mais ricas (como labels de oradores) pode melhorar a qualidade do resultado final.
- A padronização de formatos de dados entre o backend e o frontend é crucial para simplificar a integração e a manutenção do código.
- Remover funcionalidades que não são mais utilizadas pode ajudar a manter a interface mais limpa e focada nas necessidades atuais dos usuários.

## Source
https://github.com/living/livy-tldv-jobs/pull/11
