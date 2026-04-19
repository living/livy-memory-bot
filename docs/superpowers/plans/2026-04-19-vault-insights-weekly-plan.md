# vault-insights-weekly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrar `vault-insights-weekly-*` para SSOT claims (`state["claims"]`) com fallback de transição e duas saídas: pessoal (texto/Markdown) e grupo (HTML como anexo para abrir no browser).

**Architecture:** Claims-first + fallback por cobertura de janela semanal (não apenas count==0). Extração em `vault/insights/claim_inspector.py`; renderização em `vault/insights/renderers.py`; entrega via fluxo existente de envio Telegram, com grupo em `asDocument=True`.

**Tech Stack:** Python stdlib + stack atual do repo (sem novas libs).

---

## File Map

| File | Action |
|---|---|
| `vault/insights/__init__.py` | Create — exports do módulo |
| `vault/insights/claim_inspector.py` | Create — extração SSOT + fallback decision |
| `vault/insights/renderers.py` | Create — renderers personal + group HTML file |
| `vault/crons/vault_insights_weekly_generate.py` | Modify — wiring completo claims-first |
| `vault/tests/test_claim_inspector.py` | Create |
| `vault/tests/test_renderers.py` | Create |
| `vault/tests/test_vault_insights_weekly_generate.py` | Create (integração) |
| `HEARTBEAT.md` | Modify pós deploy |

---

## Task 1: claim inspector (TDD)

**Files**
- Create: `vault/insights/claim_inspector.py`
- Test: `vault/tests/test_claim_inspector.py`

- [ ] Step 1: Escrever teste falhando `test_extract_counts_by_source`
- [ ] Step 2: Escrever teste falhando `test_filters_active_and_superseded`
- [ ] Step 3: Escrever teste falhando `test_detects_contradictions_conf_delta`
- [ ] Step 4: Escrever teste falhando `test_handles_malformed_timestamps`
- [ ] Step 5: Implementar `extract_insights()` e helpers
- [ ] Step 6: Rodar `PYTHONPATH=. pytest vault/tests/test_claim_inspector.py -q`

**Notas de implementação**
- Referenciar schema canônico de `Claim` em `vault/memory_core/models.py` (não duplicar schema parcial)
- Contradições: comparar claims `status` por `entity_id` com delta de confiança > 0.3
- Tratar `superseded_by` órfão sem quebrar execução

---

## Task 2: renderers (TDD)

**Files**
- Create: `vault/insights/renderers.py`
- Test: `vault/tests/test_renderers.py`

- [ ] Step 1: Teste falhando `test_render_personal_markdown`
- [ ] Step 2: Teste falhando `test_render_personal_soft_limit_4096`
- [ ] Step 3: Teste falhando `test_render_group_html_contains_style_and_svg`
- [ ] Step 4: Implementar `render_personal(bundle)`
- [ ] Step 5: Implementar `render_group_html(bundle)` (HTML completo com `<style>` + SVG)
- [ ] Step 6: Rodar `PYTHONPATH=. pytest vault/tests/test_renderers.py -q`

**Notas de implementação**
- Personal: Markdown seguro para Telegram
- Grupo: HTML completo para browser (não parse_mode Telegram)

---

## Task 3: cron wiring claims-first + fallback robusto

**Files**
- Modify: `vault/crons/vault_insights_weekly_generate.py`
- Test: `vault/tests/test_vault_insights_weekly_generate.py`

- [ ] Step 1: Teste falhando `test_uses_ssot_claims_when_week_covered`
- [ ] Step 2: Teste falhando `test_fallback_to_markdown_when_week_not_covered`
- [ ] Step 3: Adicionar bootstrap padrão de cron (`sys.path.insert(...)`)
- [ ] Step 4: Adicionar `load_env()` padrão (`~/.openclaw/.env`)
- [ ] Step 5: Importar `load_state` de `vault.research.state_store`
- [ ] Step 6: Implementar regra de fallback por cobertura temporal semanal
- [ ] Step 7: Gerar 2 outputs (personal markdown + group html)
- [ ] Step 8: Rodar `PYTHONPATH=. pytest vault/tests/test_vault_insights_weekly_generate.py -q`

---

## Task 4: delivery

**Files**
- Modify: `vault/crons/vault_insights_weekly_generate.py` (ou helper existente no fluxo de envio)

- [ ] Step 1: Personal → enviar texto para `7426291192` (Markdown)
- [ ] Step 2: Group → salvar `living-insights-YYYY-MM-DD.html`
- [ ] Step 3: Enviar arquivo ao grupo `-5158607302` com `asDocument=True`
- [ ] Step 4: Manter dedupe para pessoal; grupo sem dedupe (decisão atual)

---

## Task 5: regressão + smoke

- [ ] Step 1: `PYTHONPATH=. pytest tests/research/ vault/tests/ -q`
- [ ] Step 2: Executar `python3 vault/crons/vault_insights_weekly_generate.py`
- [ ] Step 3: Validar presença do arquivo HTML gerado
- [ ] Step 4: Validar envio Telegram pessoal + anexo grupo

---

## Task 6: docs operacionais

- [ ] Atualizar `HEARTBEAT.md` com “insights weekly claims-first + HTML attachment”
- [ ] Registrar mudança em `memory/consolidation-log.md`

---

## Acceptance Criteria

- [ ] Pipeline lê `state["claims"]` com sucesso
- [ ] Fallback markdown dispara quando SSOT não cobre a janela semanal
- [ ] Resumo pessoal ≤ 4096 chars
- [ ] HTML do grupo é gerado como arquivo `.html` válido com CSS/SVG
- [ ] Arquivo HTML é enviado como documento Telegram ao grupo
- [ ] Supersessions/contradições aparecem em ambos outputs
- [ ] Testes novos + regressão passam
