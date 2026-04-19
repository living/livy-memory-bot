# vault-insights-weekly Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rework `vault-insights-weekly-*` to read from `state["claims"]` (wiki v2 SSOT) directly, generating two summaries: personal (text, Lincoln) and group Living (HTML+CSS+SVG).

**Architecture:** Claims-first with markdown fallback. Two renderers: dense text for personal, self-contained HTML with SVG bar charts for group. All extraction logic in `vault/ops/insights/claim_inspector.py`.

**Tech Stack:** Python stdlib only (datetime, json, pathlib). No new dependencies.

---

## File Map

| File | Action |
|---|---|
| `vault/ops/insights/__init__.py` | Create — module init |
| `vault/ops/insights/claim_inspector.py` | Create — core extraction |
| `vault/ops/insights/renderers.py` | Create — dual renderer |
| `vault/crons/vault_insights_weekly_generate.py` | Rewrite — integrate inspectors + renderers |
| `tests/ops/insights/__init__.py` | Create — test package init |
| `tests/ops/insights/test_claim_inspector.py` | Create — claim_inspector tests |
| `tests/ops/insights/test_renderers.py` | Create — renderer tests |
| `HEARTBEAT.md` | Modify — update after deploy |

---

## Task 1: `vault/ops/insights/__init__.py`

- [ ] Create `vault/ops/insights/` package init with `__all__` exports

---

## Task 2: `vault/ops/insights/claim_inspector.py`

**Files:**
- Create: `vault/ops/insights/claim_inspector.py`
- Test: `tests/ops/insights/test_claim_inspector.py`

- [ ] **Step 1: Write failing test** — `test_extract_insights_counts_by_source`

```python
from vault.ops.insights.claim_inspector import extract_insights

def test_extract_insights_counts_by_source():
    claims = [
        {"source": "github", "claim_id": "1", "entity_type": "pull_request",
         "entity_id": "r#1", "claim_type": "status", "text": "PR #1",
         "superseded_by": None, "confidence": 0.8, "event_timestamp": "2026-04-19T10:00:00+00:00"},
        {"source": "github", "claim_id": "2", "entity_type": "pull_request",
         "entity_id": "r#2", "claim_type": "status", "text": "PR #2",
         "superseded_by": None, "confidence": 0.9, "event_timestamp": "2026-04-19T11:00:00+00:00"},
        {"source": "tldv", "claim_id": "3", "entity_type": "meeting",
         "entity_id": "m#1", "claim_type": "status", "text": "Meeting 1",
         "superseded_by": None, "confidence": 0.7, "event_timestamp": "2026-04-19T12:00:00+00:00"},
    ]
    bundle = extract_insights(claims)
    assert bundle.by_source == {"github": 2, "tldv": 1}
    assert bundle.active == 3
```

- [ ] **Step 2: Write failing test** — `test_superseded_filtering`

```python
def test_superseded_filtering():
    claims = [
        {"source": "github", "claim_id": "1", "entity_type": "pull_request",
         "entity_id": "r#1", "claim_type": "status", "text": "old",
         "superseded_by": "2", "supersession_reason": "newer version",
         "confidence": 0.3, "event_timestamp": "2026-04-19T10:00:00+00:00"},
        {"source": "github", "claim_id": "2", "entity_type": "pull_request",
         "entity_id": "r#1", "claim_type": "status", "text": "new",
         "superseded_by": None, "confidence": 0.9, "event_timestamp": "2026-04-19T11:00:00+00:00"},
    ]
    bundle = extract_insights(claims)
    assert bundle.active == 1
    assert bundle.superseded_total == 1
    assert bundle.superseded_this_week[0]["supersession_reason"] == "newer version"
```

- [ ] **Step 3: Write failing test** — `test_contradiction_detection`

```python
def test_contradiction_detection():
    claims = [
        {"source": "github", "claim_id": "1", "entity_type": "pull_request",
         "entity_id": "r#1", "claim_type": "status", "text": "PR open",
         "superseded_by": None, "confidence": 0.2, "event_timestamp": "2026-04-18T10:00:00+00:00"},
        {"source": "github", "claim_id": "2", "entity_type": "pull_request",
         "entity_id": "r#1", "claim_type": "status", "text": "PR merged",
         "superseded_by": None, "confidence": 0.9, "event_timestamp": "2026-04-19T10:00:00+00:00"},
    ]
    bundle = extract_insights(claims)
    assert len(bundle.contradictions) == 1
    assert bundle.contradictions[0]["entity_id"] == "r#1"
```

- [ ] **Step 4: Implement** — `claim_inspector.py`

```python
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any

@dataclass
class InsightsBundle:
    total: int = 0
    by_source: dict[str, int] = field(default_factory=dict)
    active: int = 0
    superseded_total: int = 0
    new_this_week: dict[str, int] = field(default_factory=dict)
    superseded_this_week: list[dict] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    alerts: list[dict] = field(default_factory=list)

def _parse_ts(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))

def _count_by(items: list[dict], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        k = item.get(key, "unknown")
        out[k] = out.get(k, 0) + 1
    return out

def _find_contradictions(active: list[dict]) -> list[dict]:
    by_entity: dict[str, list[dict]] = {}
    for c in active:
        if c.get("claim_type") == "status":
            by_entity.setdefault(c["entity_id"], []).append(c)
    contradictions = []
    for entity_id, claims in by_entity.items():
        if len(claims) < 2:
            continue
        confs = [(c["confidence"], c) for c in claims]
        confs.sort(key=lambda x: x[0])
        delta = confs[-1][0] - confs[0][0]
        if delta > 0.3:
            contradictions.append({
                "entity_id": entity_id,
                "low_conf": confs[0][1],
                "high_conf": confs[-1][1],
                "delta": delta,
            })
    return contradictions

def extract_insights(claims: list[dict]) -> InsightsBundle:
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    active = [c for c in claims if not c.get("superseded_by")]
    superseded = [c for c in claims if c.get("superseded_by")]

    def this_week(c: dict) -> bool:
        return _parse_ts(c["event_timestamp"]) >= week_ago

    active_this_week = [c for c in active if this_week(c)]
    sup_this_week = [c for c in superseded if this_week(c)]

    alerts = []
    new_by_source = _count_by(active_this_week, "source")
    sup_count = len(sup_this_week)
    if sup_count > 5:
        alerts.append({"type": "high_supersession_rate", "count": sup_count})

    return InsightsBundle(
        total=len(claims),
        by_source=_count_by(claims, "source"),
        active=len(active),
        superseded_total=len(superseded),
        new_this_week=new_by_source,
        superseded_this_week=sup_this_week,
        contradictions=_find_contradictions(active),
        alerts=alerts,
    )
```

- [ ] **Step 5: Run tests** — `PYTHONPATH=. pytest tests/ops/insights/test_claim_inspector.py -v`

---

## Task 3: `vault/ops/insights/renderers.py`

**Files:**
- Create: `vault/ops/insights/renderers.py`
- Test: `tests/ops/insights/test_renderers.py`

- [ ] **Step 1: Write failing test** — `test_render_personal`

```python
from vault.ops.insights.claim_inspector import InsightsBundle
from vault.ops.insights.renderers import render_personal

def test_render_personal():
    bundle = InsightsBundle(
        total=3,
        by_source={"github": 2, "tldv": 1},
        active=3,
        superseded_total=1,
        new_this_week={"github": 2, "tldv": 1},
        superseded_this_week=[],
        contradictions=[],
        alerts=[],
    )
    text = render_personal(bundle)
    assert "github 2" in text
    assert "tldv 1" in text
    assert "Ativos:  3" in text
```

- [ ] **Step 2: Write failing test** — `test_render_group_html`

```python
from vault.ops.insights.claim_inspector import InsightsBundle
from vault.ops.insights.renderers import render_group_html

def test_render_group_html():
    bundle = InsightsBundle(
        total=3,
        by_source={"github": 2, "tldv": 1},
        active=3,
        superseded_total=0,
        new_this_week={"github": 2, "tldv": 1},
        superseded_this_week=[],
        contradictions=[],
        alerts=[],
    )
    html = render_group_html(bundle)
    assert "<html>" in html
    assert "text/html" in html or "<body" in html
    assert "github" in html
```

- [ ] **Step 3: Implement** — `render_personal`

```python
def render_personal(bundle: InsightsBundle) -> str:
    lines = [
        f"🧠 Insights Semanais — Lincoln",
        f"FONTES: " + " | ".join(f"{k} {v}" for k, v in sorted(bundle.by_source.items())),
        f"ATIVOS:  {bundle.active}  |  SUPERSEDED: {bundle.superseded_total}",
        "",
    ]
    if bundle.new_this_week:
        lines.append("── NOVOS ESTA SEMANA ──")
        for src, count in sorted(bundle.new_this_week.items()):
            lines.append(f"+ {src}: {count}")
        lines.append("")
    if bundle.superseded_this_week:
        lines.append("── SUPERSESSIONS ──")
        for c in bundle.superseded_this_week:
            lines.append(f"⚠️  {c['claim_id']} — {c.get('supersession_reason', 'n/a')}")
        lines.append("")
    if bundle.contradictions:
        lines.append("── CONTRADIÇÕES ──")
        for c in bundle.contradictions:
            lines.append(f"? {c['entity_id']} — delta conf {c['delta']:.2f}")
        lines.append("")
    if bundle.alerts:
        lines.append("── ALERTS ──")
        for a in bundle.alerts:
            lines.append(f"⚠️  {a}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Implement** — `render_group_html` (SVG bar chart + CSS inline)

```python
def _svg_bar_chart(by_source: dict[str, int]) -> str:
    """Generate inline SVG horizontal bar chart."""
    if not by_source:
        return ""
    max_val = max(by_source.values())
    colors = {"github": "#4a90d9", "tldv": "#50c878", "trello": "#f5a623"}
    rows = []
    y = 0
    for src, count in sorted(by_source.items()):
        width = int(280 * count / max_val) if max_val else 0
        color = colors.get(src, "#999999")
        rows.append(
            f'<rect x="0" y="{y}" width="{width}" height="18" fill="{color}"/>'
            f'<text x="{width + 6}" y="{y + 14}" font-size="12">{src}: {count}</text>'
        )
        y += 26
    height = y + 4
    return (
        f'<svg viewBox="0 0 300 {height}" '
        f'style="font-family:sans-serif;font-size:12px">'
        + "".join(rows) + "</svg>"
    )

def render_group_html(bundle: InsightsBundle) -> str:
    chart = _svg_bar_chart(bundle.by_source)
    supersessions_html = ""
    if bundle.superseded_this_week:
        items = "".join(
            f"<li><b>{c['source']}</b>: {c.get('text','')[:80]} "
            f"<small>(superseded: {c.get('supersession_reason','n/a')})</small></li>"
            for c in bundle.superseded_this_week[:5]
        )
        supersessions_html = f"<h3>Supersessions</h3><ul>{items}</ul>"
    alerts_html = ""
    if bundle.alerts:
        items = "".join(f"<li>⚠️ {a}</li>" for a in bundle.alerts)
        alerts_html = f"<h3>Alerts</h3><ul>{items}</ul>"
    html = (
        "<!DOCTYPE html><html><body style=\"font-family:sans-serif;"
        "background:#f9f9f9;color:#222;max-width:480px;padding:12px\">"
        f"<h2>🧠 Living Insights | Semana</h2>"
        f"<h3>Atividade por Fonte</h3>{chart}"
        f"<h3>Ativos: {bundle.active} | Superseded: {bundle.superseded_total}</h3>"
        f"{supersessions_html}{alerts_html}"
        "</body></html>"
    )
    return html
```

- [ ] **Step 5: Run tests** — `PYTHONPATH=. pytest tests/ops/insights/test_renderers.py -v`

---

## Task 4: Rewrite `vault/crons/vault_insights_weekly_generate.py`

**Files:**
- Modify: `vault/crons/vault_insights_weekly_generate.py`
- Reference: `vault/ops/insights/claim_inspector.py`, `vault/ops/insights/renderers.py`

- [ ] **Step 1: Write failing integration test** — `test_generate_claims_first`

```python
# tests/ops/insights/test_e2e.py
def test_generate_claims_first(tmp_path, monkeypatch):
    # Setup fake state with claims
    fake_state = {"claims": [...], "processed_event_keys": {...}}
    # Patch load_state / save_state
    # Run generate
    # Assert personal and group outputs are non-empty
```

- [ ] **Step 2: Rewrite cron** — replace existing `genera_insights()` calls with:

```python
# At top of generate_insights():
from vault.research.state_store import load_state
from vault.ops.insights.claim_inspector import extract_insights
from vault.ops.insights.renderers import render_personal, render_group_html

SSOT_PATH = Path("state/identity-graph/state.json")
STATE = load_state(SSOT_PATH)
CLAIMS = STATE.get("claims", [])

# Fallback to markdown blobs if SSOT empty
if not CLAIMS:
    blobs = glob("memory/vault/claims/*.md")
    CLAIMS = _parse_markdown_blobs(blobs)

bundle = extract_insights(CLAIMS)
personal_text = render_personal(bundle)
group_html = render_group_html(bundle)
```

- [ ] **Step 3: Wire delivery** — ensure both outputs are sent via Telegram:
- Personal text → `7426291192` (existing logic)
- Group HTML → `-5158607302` with `parse_mode="HTML"`

- [ ] **Step 4: Run existing test suite** — `PYTHONPATH=. pytest tests/research/ tests/ops/ -q`

---

## Task 5: End-to-end smoke

- [ ] Run `python3 vault/crons/vault_insights_weekly_generate.py` locally
- [ ] Verify both personal text and HTML are non-empty
- [ ] Verify HTML contains `<svg>` and `font-family`

---

## Task 6: Update HEARTBEAT.md

- [ ] Add entry for vault-insights-weekly with claims-first note
- [ ] Commit
