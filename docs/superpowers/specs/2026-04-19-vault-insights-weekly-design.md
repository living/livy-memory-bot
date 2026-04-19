# Spec: vault-insights-weekly com SSOT Claims

## Overview

Rework do pipeline `vault-insights-weekly-*` para ler directamente de `state["claims"]`
(wiki v2) em vez de parsear markdown blobs. Fallback para markdown durante transição.
Gera dois resumos distintos: pessoal (Lincoln) e grupo Living (HTML).

---

## 1. Fontes de Dados

### Primary: SSOT claims
```python
from vault.research.state_store import load_state
state = load_state("state/identity-graph/state.json")
claims = state.get("claims", [])
```

Schema canônico de claim: `vault/memory_core/models.py` (`Claim`, `SourceRef`, `AuditTrail`).
Evitar duplicar schema parcial no código de extração.

### Fallback: markdown blobs
```python
blobs = glob("memory/vault/claims/*.md")
```
Usado quando SSOT não cobre adequadamente a janela semanal (fallback por cobertura temporal, não só count).

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

**Formato:** HTML completo autocontido (ficheiro `.html` anexo ao Telegram).

O ficheiro é gerado como `living-insights-YYYY-MM-DD.html` e enviado como documento Telegram
(`sendDocument` / `send` com `asDocument=True`). O utilizador abre no browser.
Sem restrições de parse_mode — HTML/CSS/SVG completo é permitido em anexo.

**Estrutura:**
- Barra superior com título + data
- Gráfico de barras por fonte (SVG com CSS real)
- Secção novos eventos
- Secção supersessions
- Secção alertas
- Footer com timestamp de geração

**CSS:** `<style>` block normal dentro do HTML (sem restrições em anexo).

---

## 4. Pipeline de extracção

### `vault/insights/claim_inspector.py`

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

### `vault/insights/renderers.py`

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
| `vault/insights/claim_inspector.py` | **NOVO** — extraccao de insights (em `vault/insights/` junto de `envia_resumo.py`) |
| `vault/insights/renderers.py` | **NOVO** — personal text + group HTML renderers |
| `vault/insights/__init__.py` | **NOVO** — modulo init |
| `vault/crons/vault_insights_weekly_generate.py` | Rewrite: claims-first + dual renderer |
| `vault/tests/test_claim_inspector.py` | **NOVO** — testes |
| `vault/tests/test_renderers.py` | **NOVO** — testes |
| `HEARTBEAT.md` | Actualizar after deploy |

---

## 6. Entrega

### Lincoln (pessoal)
- **Canal:** Telegram direct (`7426291192`)
- **Tipo:** texto estructurado com emoji (Markdown)
- **Mesmo mecanismo dedupe** existente em `envia_resumo.py`

### Grupo Living
- **Canal:** Telegram group (`-5158607302`)
- **Tipo:** documento HTML (anexo `living-insights-YYYY-MM-DD.html`)
- **Sem dedupe** (group quer ver sempre o resumo)
- **Envio:** `sendDocument` / `send(..., asDocument=True)`

---

## 7. Criterios de aceite

- [ ] `vault_insights_weekly_generate` le `state["claims"]` sem errors
- [ ] Fallback para markdown funciona quando SSOT não tem dados no range da semana
- [ ] Resumo pessoal renderiza < 4096 caracteres (limite Telegram direct)
- [ ] HTML grupo gerado como ficheiro `.html` com CSS+SVG completo
- [ ] Ficheiro HTML enviado como documento Telegram ao grupo Living
- [ ] Supersessions aparecem em ambas as versões
- [ ] Testes cobrem `claim_inspector` e ambos renderers
- [ ] Cron existing `vault-insights-weekly-generate` continua a funcionar

---

## 8. Runtime & Dependencias

- Cron segue padrão do repo com bootstrap `sys.path.insert(0, str(Path(__file__).resolve().parents[2]))`
- Carregamento de env via `load_env()` (`~/.openclaw/.env`) igual aos crons operacionais
- Nenhuma nova library. Gráfico em SVG no HTML (arquivo anexo). Parsing de datas com `datetime.fromisoformat()`.
