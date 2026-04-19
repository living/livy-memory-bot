# Spec: vault-insights-weekly com SSOT Claims

## Overview

Rework do pipeline `vault-insights-weekly-*` para ler directamente de `state["claims"]`
(wiki v2) em vez de parsear markdown blobs. Fallback para markdown durante transição.
Gera dois resumos distintos: pessoal (Lincoln) e grupo Living (HTML).

---

## 1. Fontes de Dados

### Primary: SSOT claims
```python
state = load_state("state/identity-graph/state.json")
claims = state.get("claims", [])
```

Formato de cada claim:
```json
{
  "claim_id": "uuid",
  "entity_type": "pull_request | meeting | card | ...",
  "entity_id": "living/repo#42 | meeting_id | card_id",
  "claim_type": "status | timeline_event | decision | ...",
  "text": "PR #42: fix bug no parser",
  "source": "github | tldv | trello",
  "confidence": 0.85,
  "superseded_by": null | "claim_id",
  "supersession_reason": null | "superseded by newer claim",
  "event_timestamp": "2026-04-19T...",
  ...
}
```

### Fallback: markdown blobs
```python
blobs = glob("memory/vault/claims/*.md")
```
Usado apenas quando `len(claims) == 0`.

---

## 2. Filtros sobre Claims

### Ativas vs Superseded
- **Ativa**: `superseded_by is None`
- **Superseded**: `superseded_by is not None`

### Janela temporal (semana transactada)
```python
week_ago = utc_now() - timedelta(days=7)
active_this_week = [
  c for c in active_claims
  if parse_iso(c["event_timestamp"]) >= week_ago
]
superseded_this_week = [
  c for c in superseded_claims
  if parse_iso(c["event_timestamp"]) >= week_ago
]
```

### Contradições
Claims para a mesma `entity_id` com `claim_type=status` e `confidence` delta > 0.3
entre o mais recente e o mais antigo.

---

## 3. Secções do Resumo

### 3.1 Resumo Pessoal (Lincoln — Telegram direct)

Formato: texto estruturado, tipo:

```
🧠 Insights Semanais — Lincoln
2026-04-14 → 2026-04-19

Fontes: github 33 | tldv 7 | trello 390
Ativos:  427  |  Superseded: 3

── Novos (github) ──
+ PR #19 @livy-memory-bot: GitHub Rich PR Events
+ PR #18 @livy-memory-bot: batch-first research pipeline
...

── Supersessions ──
⚠️ claim abc123 (PR #2) superseded by def456
   razão: newer PR for same entity

── Contradições Detectadas ──
? entity living/livy-memory-bot#2 — 2 claims com conf delta 0.4
  claim 1 (conf=0.3): "initial PR"
  claim 2 (conf=0.7): "updated after review"

── Alerts ──
🔴 trello: 3 supersessions esta semana (taxa elevada)
```

### 3.2 Resumo Grupo Living (Telegram group — HTML autocontido)

**Formato:** `text/html` com CSS inline (sem external deps).

**Estrutura:**
```
┌─────────────────────────────────────┐
│ 🧠 Living Insights  |  14-19 Apr   │
├─────────────────────────────────────┤
│ ATIVIDADE POR FONTE                 │
│ [grafico barras: github/tldv/trello]│
├─────────────────────────────────────┤
│ NOVOS EVENTOS                       │
│ • PR #19 — GitHub Rich PR Events    │
│ • 8 meetings processados           │
│ • 12 cards atualizados              │
├─────────────────────────────────────┤
│ SUPERSESSIONS                       │
│ (lista de claims superseded)        │
├─────────────────────────────────────┤
│ ALERTAS                             │
│ (se há anomalies)                  │
└─────────────────────────────────────┘
```

**Gráficos:** SVG inline (sem JS, sem bibliotecas externas).
Exemplo — barras horizontais em SVG:
```svg
<svg viewBox="0 0 300 80" style="font-family:sans-serif;font-size:12px">
  <rect x="0"   y="10" width="200" height="16" fill="#4a90d9"/>
  <text x="205" y="22">GitHub: 33</text>
  <rect x="0"   y="35" width="40"  height="16" fill="#50c878"/>
  <text x="45"  y="47">TLDV: 7</text>
  <rect x="0"   y="60" width="180" height="16" fill="#f5a623"/>
  <text x="185" y="72">Trello: 390</text>
</svg>
```

**CSS inline** (`style="..."` em cada tag, sem `<style>` block).

---

## 4. Pipeline de extracção

### `vault/ops/insights/claim_inspector.py`

```python
def extract_insights(claims: list[dict]) -> InsightsBundle:
    """Core extraction from SSOT claims."""
    active = [c for c in claims if not c.get("superseded_by")]
    superseded = [c for c in claims if c.get("superseded_by")]

    week_ago = utc_now() - timedelta(days=7)
    this_week = lambda c: parse_iso(c["event_timestamp"]) >= week_ago

    return InsightsBundle(
        total=len(claims),
        by_source=count_by(claims, "source"),
        active=len(active),
        superseded_total=len(superseded),
        new_this_week=count_by(filter(active, this_week), "source"),
        superseded_this_week=filter(superseded, this_week),
        contradictions=_find_contradictions(active),
        alerts=_alerts_from_stats(...),
    )
```

### `vault/ops/insights/renderers.py`

```python
def render_personal(bundle: InsightsBundle) -> str:
    """Texto estruturado para Telegram direct."""

def render_group_html(bundle: InsightsBundle) -> str:
    """HTML autocontido com CSS inline e gráficos SVG para Telegram group."""
```

---

## 5. Ficheiros

| Ficheiro | Mudanca |
|---|---|
| `vault/crons/vault_insights_weekly_generate.py` | Rewrite: claims-first + dual renderer |
| `vault/ops/insights/claim_inspector.py` | **NOVO** — extraccao de insights |
| `vault/ops/insights/renderers.py` | **NOVO** — personal + group_html renderers |
| `vault/ops/insights/__init__.py` | **NOVO** — modulo init |
| `tests/ops/insights/test_claim_inspector.py` | **NOVO** — testes |
| `tests/ops/insights/test_renderers.py` | **NOVO** — testes |
| `HEARTBEAT.md` | Actualizar after deploy |

---

## 6. Entrega

### Lincoln (pessoal)
- **Canal:** Telegram direct (`7426291192`)
- **Tipo:** texto estructurado
- **Mesmo mecanismo dedupe** existente em `envia_resumo.py`

### Grupo Living
- **Canal:** Telegram group (`-5158607302`)
- **Tipo:** `text/html`
- **Sem dedupe** (group quer ver sempre o resumo)

---

## 7. Criterios de aceite

- [ ] `vault_insights_weekly_generate` le `state["claims"]` sem errors
- [ ] Fallback para markdown funciona quando SSOT vazio
- [ ] Resumo pessoal renderiza < 2000 caracteres (limite Telegram)
- [ ] HTML grupo renderiza correctamente no Telegram (CSS inline + SVG)
- [ ] Supersessions aparecem em ambas as versões
- [ ] Testes cobrem `claim_inspector` e ambos renderers
- [ ] Cron existing `vault-insights-weekly-generate` continua a funcionar

---

## 8. Dependencias

Nenhuma nova library. Grafico em SVG puro (stdlib). Parsing de datas com `datetime.fromisoformat()`.
