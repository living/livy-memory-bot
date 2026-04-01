# Learned Rules — Livy Memory Agent

Gerado por: learn_from_feedback.py
Atualizado: 2026-03-31

## Regras com score positivo (manter padrão)
_Nenhuma regra aprendida ainda._

## Regras com score negativo (evitar)
- `202603312304:tldv-pipeline-state.md`: score -1 (0✍ 1✎)
  Notas: "Os problemas reportados em status e decision estão outdated"

## Regras neutras (experimentar abordagens alternativas)
- `tldv-enrichment-feedback-loop.md`
  Descrição: Feedback do usuário na skill meetings-tldv sobre reuniões erradas ou topics/decisions imprecisos deve circular de volta para a pipeline do tldv (livy-tldv-jobs). A lógica atual de `enrichment_context` (PRs e Cards) está muito ampla — retorna últimos 7 dias em vez de filtrar por contexto da reunião. Falta popular `meeting_participants`.
  Contexto: Reunião "Status" de 31/03 tinha 12 PRs e 15 cards, nenhum específico da reunião. Tabela `summaries` pode estar vazia para algumas reuniões apesar de `enriched_at` preenchido.

---
_score = thumbs_up - thumbs_down por tipo de ação_