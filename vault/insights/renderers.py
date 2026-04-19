"""Render weekly insights for personal Telegram and group HTML document."""

from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from vault.insights.claim_inspector import InsightsBundle


def _safe(v: object) -> str:
    return escape(str(v))


def render_personal(bundle: InsightsBundle) -> str:
    """Structured markdown-like text for personal Telegram direct message."""
    lines: list[str] = [
        "🧠 Insights Semanais — Lincoln",
        f"{bundle.week_start} → {bundle.week_end}",
        "",
        "Fontes: " + " | ".join(f"{src} {count}" for src, count in sorted(bundle.by_source.items())),
        f"Ativos: {bundle.active} | Superseded: {bundle.superseded_total}",
        "",
        "── Novos (esta semana) ──",
    ]

    if bundle.new_this_week:
        for src, count in sorted(bundle.new_this_week.items()):
            lines.append(f"+ {src}: {count}")
    else:
        lines.append("+ sem novos itens")

    lines.extend(["", "── Supersessions ──"])
    if bundle.superseded_this_week:
        for item in bundle.superseded_this_week[:10]:
            cid = item.get("claim_id", "?")
            newer = item.get("superseded_by", "?")
            reason = item.get("supersession_reason", "n/a")
            lines.append(f"⚠️ claim {cid} superseded by {newer}")
            lines.append(f"   razão: {reason}")
    else:
        lines.append("✅ sem supersessions na semana")

    lines.extend(["", "── Contradições Detectadas ──"])
    if bundle.contradictions:
        for c in bundle.contradictions[:8]:
            old_conf = c.claim_old.get("confidence", 0.0)
            new_conf = c.claim_new.get("confidence", 0.0)
            lines.append(f"? entity {c.entity_id} — delta {c.delta:.2f}")
            lines.append(f"  claim old (conf={old_conf}): {str(c.claim_old.get('text', ''))[:120]}")
            lines.append(f"  claim new (conf={new_conf}): {str(c.claim_new.get('text', ''))[:120]}")
    else:
        lines.append("✅ nenhuma contradição relevante")

    lines.extend(["", "── Alerts ──"])
    if bundle.alerts:
        for alert in bundle.alerts[:8]:
            emoji = "🔴" if alert.level == "critical" else "⚠️"
            lines.append(f"{emoji} {alert.message}")
    else:
        lines.append("✅ sem alertas")

    text = "\n".join(lines)
    if len(text) > 4096:
        text = text[:4050] + "\n\n…(truncated)"
    return text


def render_group_html(bundle: InsightsBundle) -> str:
    """Full self-contained HTML with inline CSS and SVG chart."""
    source_items = sorted(bundle.by_source.items())
    max_count = max((count for _, count in source_items), default=1)

    bar_width = 120
    gap = 24
    left = 40
    chart_height = 220
    base_y = 250
    svg_width = max(600, left + len(source_items) * (bar_width + gap) + 40)
    svg_height = 300

    bars: list[str] = []
    labels: list[str] = []

    for idx, (source, count) in enumerate(source_items):
        height = int((count / max_count) * chart_height) if max_count else 0
        x = left + idx * (bar_width + gap)
        y = base_y - height
        bars.append(
            f'<rect x="{x}" y="{y}" width="{bar_width}" height="{height}" rx="8" class="bar" />'
            f'<text x="{x + bar_width / 2}" y="{y - 8}" text-anchor="middle" class="value">{count}</text>'
        )
        labels.append(
            f'<text x="{x + bar_width / 2}" y="{base_y + 22}" text-anchor="middle" class="label">{_safe(source)}</text>'
        )

    superseded_items = "".join(
        f"<li><strong>{_safe(item.get('claim_id', '?'))}</strong> → {_safe(item.get('superseded_by', '?'))}"
        f" <em>{_safe(item.get('supersession_reason', 'n/a'))}</em></li>"
        for item in bundle.superseded_this_week[:15]
    ) or "<li>Sem supersessions na semana.</li>"

    contradictions = "".join(
        "<li>"
        f"<strong>{_safe(c.entity_id)}</strong> (delta={c.delta:.2f})"
        f"<br><small>old={_safe(c.claim_old.get('text', ''))}</small>"
        f"<br><small>new={_safe(c.claim_new.get('text', ''))}</small>"
        "</li>"
        for c in bundle.contradictions[:12]
    ) or "<li>Sem contradições relevantes.</li>"

    alerts = "".join(
        f"<li class=\"alert { _safe(a.level) }\">{_safe(a.message)}</li>"
        for a in bundle.alerts[:12]
    ) or "<li class=\"alert ok\">Sem alertas.</li>"

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!DOCTYPE html>
<html lang=\"pt-BR\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Living Insights Semanais</title>
  <style>
    :root {{
      --bg: #0f172a;
      --card: #111827;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --accent: #22c55e;
      --warn: #f59e0b;
      --critical: #ef4444;
    }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 24px; background: var(--bg); color: var(--text); font: 14px/1.5 Inter, system-ui, sans-serif; }}
    .wrap {{ max-width: 1100px; margin: 0 auto; }}
    .top {{ display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 16px; }}
    h1 {{ margin: 0; font-size: 24px; }}
    .muted {{ color: var(--muted); }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; }}
    .card {{ background: var(--card); border: 1px solid #1f2937; border-radius: 12px; padding: 14px; }}
    .stats {{ display: flex; gap: 18px; margin-top: 10px; }}
    .stat strong {{ display: block; font-size: 22px; }}
    svg {{ width: 100%; height: auto; background: #0b1220; border-radius: 10px; border: 1px solid #1f2937; }}
    .bar {{ fill: #2563eb; }}
    .label {{ fill: #94a3b8; font-size: 12px; }}
    .value {{ fill: #e2e8f0; font-size: 12px; }}
    ul {{ margin: 10px 0 0; padding-left: 18px; }}
    .alert.warning {{ color: var(--warn); }}
    .alert.critical {{ color: var(--critical); }}
    .alert.ok {{ color: var(--accent); }}
    footer {{ margin-top: 18px; color: var(--muted); font-size: 12px; }}
  </style>
</head>
<body>
  <div class=\"wrap\">
    <div class=\"top\">
      <h1>📊 Living Insights Semanais</h1>
      <div class=\"muted\">{_safe(bundle.week_start)} → {_safe(bundle.week_end)}</div>
    </div>

    <div class=\"card\">
      <div class=\"stats\">
        <div class=\"stat\"><span class=\"muted\">Total claims</span><strong>{bundle.total}</strong></div>
        <div class=\"stat\"><span class=\"muted\">Ativos</span><strong>{bundle.active}</strong></div>
        <div class=\"stat\"><span class=\"muted\">Superseded</span><strong>{bundle.superseded_total}</strong></div>
      </div>
    </div>

    <div class=\"card\" style=\"margin-top:14px;\">
      <h2>Fontes</h2>
      <svg viewBox=\"0 0 {svg_width} {svg_height}\" xmlns=\"http://www.w3.org/2000/svg\" role=\"img\" aria-label=\"Claims por fonte\">
        <line x1=\"30\" y1=\"250\" x2=\"{svg_width - 20}\" y2=\"250\" stroke=\"#334155\" />
        {''.join(bars)}
        {''.join(labels)}
      </svg>
    </div>

    <div class=\"grid\" style=\"margin-top:14px;\">
      <section class=\"card\">
        <h3>Novos eventos (semana)</h3>
        <ul>
          {''.join(f'<li>{_safe(src)}: {count}</li>' for src, count in sorted(bundle.new_this_week.items())) or '<li>Sem novos eventos.</li>'}
        </ul>
      </section>

      <section class=\"card\">
        <h3>Supersessions</h3>
        <ul>{superseded_items}</ul>
      </section>

      <section class=\"card\">
        <h3>Contradições</h3>
        <ul>{contradictions}</ul>
      </section>

      <section class=\"card\">
        <h3>Alertas</h3>
        <ul>{alerts}</ul>
      </section>
    </div>

    <footer>Gerado automaticamente em {generated_at}</footer>
  </div>
</body>
</html>
"""
