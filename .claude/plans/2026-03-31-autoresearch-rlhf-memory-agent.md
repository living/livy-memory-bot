# Autoresearch + RLHF para o Agente de Memória — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o loop de autoresearch hourly com feedback RLHF via botões 👍/👎 no Telegram. O agente de memória evolui com o tempo baseado no feedback do usuário.

**Architecture:** Sistema de 5 componentes: (1) scripts de métricas para as 4 dimensões de qualidade, (2) script de verificação para o loop do autoresearch, (3) script de aprendizado do feedback, (4) polling daemon para receber callbacks do Telegram, (5) cron configurado para rodar a cada 1 hora.

**Tech Stack:** Python 3, Telegram Bot API (python-telegram-bot ou requests direto), OpenClaw cron, JSONL para feedback log.

---

## Mapa de Arquivos

```
workspace-livy-memory/
├── skills/memoria-consolidation/
│   ├── consolidate.py          # existente
│   ├── SKILL.md               # existente
│   ├── autoresearch_metrics.py  # NOVO — métricas das 4 dimensões
│   ├── autoresearch_verify.py  # NOVO — verificação por dimensão
│   └── learn_from_feedback.py  # NOVO — feedback → learned-rules.md
├── handlers/
│   └── feedback_poller.py      # NOVO — polling Telegram callback queries
├── memory/
│   ├── feedback-log.jsonl      # NOVO — log de feedback do usuário
│   └── learned-rules.md        # NOVO — regras extraídas do feedback
└── docs/superpowers/plans/     # este arquivo
```

**Arquivo de credentials** (referência, não criar):
- Bot token: `8738927361:AAFIG5E9-ND9hwb2onxbLLBi03aQZzofuoE` (Telegram `livy-memory-feed`)
- DM para: Lincoln (tg:7426291192)

---

## Task 1: autoresearch_metrics.py

**Files:**
- Create: `skills/memoria-consolidation/autoresearch_metrics.py`

**Resumo:** Script que calcula scores para as 4 dimensões de qualidade. Executado no início de cada iteração do autoresearch.

```python
#!/usr/bin/env python3
"""
Autoresearch Metrics — 4 dimensões de qualidade para o agente de memória.

Dimensões:
  --metric completeness  Score 0-10 por topic file (checklist)
  --metric crossrefs    Contagem de cross-references entre topic files
  --metric actions      Ações automáticas por execução (dry-run do consolidate)
  --metric interventions Intervenções manuais necessárias
  --all                 Todas as métricas
"""

import re, sys, json
from pathlib import Path
from datetime import datetime

MEMORY_DIR = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory")
CURATED_DIR = MEMORY_DIR / "curated"
ARCHIVE_DIR = MEMORY_DIR / ".archive"

def completeness_score(fpath):
    """Calcula score 0-10 de completude de um topic file."""
    try:
        content = fpath.read_text()
    except:
        return 0.0
    score = 0.0
    # frontmatter name, description, type
    if re.search(r'^---\n.*?\nname:\s+\S+', content, re.M):
        score += 2
    if re.search(r'^---\n.*?\ndescription:\s+\S+', content, re.M):
        score += 2
    if re.search(r'^---\n.*?\ntype:\s+\S+', content, re.M):
        score += 2
    # date
    if re.search(r'^---\n.*?\ndate:\s+\S+', content, re.M):
        score += 2
    # decisão registrada
    if re.search(r'(?i)(decisão|decision|registrada)', content):
        score += 2
    return score

def crossref_count():
    """Conta cross-references entre topic files em curated/."""
    if not CURATED_DIR.exists():
        return 0
    count = 0
    for f in CURATED_DIR.glob("*.md"):
        content = f.read_text()
        refs = re.findall(r'\[([^\]]+)\]\(memory/curated/([^)]+)\)', content)
        count += len(refs)
    return count

def consolidation_actions_count():
    """Simula consolidate.py em dry-run e conta ações que seriam feitas."""
    # importa dinamicamente para não duplicar lógica
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from consolidate import gather_signal, load_memory_index
    except ImportError:
        return 0
    try:
        _, referenced = load_memory_index()
        signals = gather_signal(referenced)
        actions = (len(signals["relative_dates"])
                   + len(signals["stale"])
                   + len(signals["orphaned"]))
        return actions
    except:
        return 0

def interventions_count():
    """Conta entradas no consolidation-log.md que requerem atenção humana."""
    log = MEMORY_DIR / "consolidation-log.md"
    if not log.exists():
        return 0
    content = log.read_text()
    # conta linhas com ⚠️ (requer revisão manual)
    return content.count("⚠️")

def main():
    metric = sys.argv[1] if len(sys.argv) > 1 else "--all"
    result = {}

    if metric == "--all":
        result["completeness"] = completeness_score(CURATED_DIR / "dummy.md")  # placeholder
        # average completeness across all topic files
        if CURATED_DIR.exists():
            scores = [completeness_score(f) for f in CURATED_DIR.glob("*.md")]
            result["completeness_avg"] = round(sum(scores)/len(scores), 2) if scores else 0.0
        else:
            result["completeness_avg"] = 0.0
        result["crossrefs"] = crossref_count()
        result["actions"] = consolidation_actions_count()
        result["interventions"] = interventions_count()
        print(json.dumps(result, indent=2))
    elif metric == "completeness":
        if CURATED_DIR.exists():
            scores = {f.name: completeness_score(f) for f in CURATED_DIR.glob("*.md")}
            print(json.dumps(scores, indent=2))
        else:
            print("{}")
    elif metric == "crossrefs":
        print(crossref_count())
    elif metric == "actions":
        print(consolidation_actions_count())
    elif metric == "interventions":
        print(interventions_count())
    else:
        print(f"Unknown metric: {metric}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

- [ ] **Step 1: Criar o esqueleto do arquivo com docstring e imports**
- [ ] **Step 2: Implementar completeness_score() — checklist 0-10**
- [ ] **Step 3: Implementar crossref_count()**
- [ ] **Step 4: Implementar consolidation_actions_count() (importa consolidate.py)**
- [ ] **Step 5: Implementar interventions_count()**
- [ ] **Step 6: Implementar main() com parsing de --metric e --all**
- [ ] **Step 7: Testar python3 autoresearch_metrics.py --all**
- [ ] **Step 8: Testar python3 autoresearch_metrics.py --metric crossrefs**
- [ ] **Step 9: Commit**

---

## Task 2: autoresearch_verify.py

**Files:**
- Create: `skills/memoria-consolidation/autoresearch_verify.py`

**Resumo:** Script de verificação executado pelo autoresearch loop após cada modificação. Retorna o valor numérico da métrica para que o loop possa comparar antes/depois.

```python
#!/usr/bin/env python3
"""
Autoresearch Verify — verificação de métrica após modificação.

Uso:
  python3 autoresearch_verify.py --metric completeness
  python3 autoresearch_verify.py --metric crossrefs
  python3 autoresearch_verify.py --metric actions
  python3 autoresearch_verify.py --metric interventions

Retorna o valor numérico (para comparação before/after no loop).
"""

import sys, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from autoresearch_metrics import (
    completeness_score, crossref_count,
    consolidation_actions_count, interventions_count,
    CURATED_DIR, MEMORY_DIR
)

METRIC_MAP = {
    "completeness": lambda: completeness_score(CURATED_DIR / "dummy.md"),  # placeholder
    "crossrefs": crossref_count,
    "actions": consolidation_actions_count,
    "interventions": interventions_count,
}

def main():
    if len(sys.argv) < 3 or sys.argv[1] != "--metric":
        print("Usage: autoresearch_verify.py --metric <name>", file=sys.stderr)
        sys.exit(1)
    metric = sys.argv[2]
    if metric not in METRIC_MAP:
        print(f"Unknown metric: {metric}", file=sys.stderr)
        sys.exit(1)

    # Para completeness, retorna a média de todos os topic files
    if metric == "completeness":
        if CURATED_DIR.exists():
            scores = [completeness_score(f) for f in CURATED_DIR.glob("*.md")]
            val = round(sum(scores)/len(scores), 2) if scores else 0.0
        else:
            val = 0.0
    else:
        val = METRIC_MAP[metric]()

    print(val)

if __name__ == "__main__":
    main()
```

- [ ] **Step 1: Criar esqueleto com imports de autoresearch_metrics**
- [ ] **Step 2: Implementar parsing --metric e delegação**
- [ ] **Step 3: Testar python3 autoresearch_verify.py --metric crossrefs**
- [ ] **Step 4: Commit**

---

## Task 3: feedback-log.jsonl e learned-rules.md

**Files:**
- Create: `memory/feedback-log.jsonl` (vazio, só headers)
- Create: `memory/learned-rules.md` (template inicial)

**feedback-log.jsonl** — arquivo vazio, criado na primeira execução:
```
(no content — append only)
```

**learned-rules.md** — template:
```markdown
# Learned Rules — Livy Memory Agent

Gerado por: learn_from_feedback.py
Atualizado: (date)

## Regras com score positivo (manter padrão)
_Nenhuma regra aprendida ainda._

## Regras com score negativo (evitar)
_Nenhuma regra aprendida ainda._

## Regras neutras (experimentar aborduras alternativas)
_Nenhuma regra aprendida ainda._

---
_score = thumbs_up - thumbs_down por tipo de ação_
```

- [ ] **Step 1: Criar memory/feedback-log.jsonl (vazio)**
- [ ] **Step 2: Criar memory/learned-rules.md com template**
- [ ] **Step 3: Commit**

---

## Task 4: learn_from_feedback.py

**Files:**
- Create: `skills/memoria-consolidation/learn_from_feedback.py`

**Resumo:** Lê feedback-log.jsonl, calcula score por tipo de ação, gera/atualiza learned-rules.md.

```python
#!/usr/bin/env python3
"""
Learn from Feedback — processa feedback-log.jsonl e gera learned-rules.md.

Uso:
  python3 learn_from_feedback.py

Lê:  memory/feedback-log.jsonl
Escreve: memory/learned-rules.md
"""

import json, sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

MEMORY_DIR = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory")
FEEDBACK_LOG = MEMORY_DIR / "feedback-log.jsonl"
LEARNED_RULES = MEMORY_DIR / "learned-rules.md"

ACTION_SCORES = defaultdict(lambda: {"up": 0, "down": 0, "null": 0})
ACTION_NOTES = defaultdict(list)

def load_feedback():
    if not FEEDBACK_LOG.exists():
        return
    with FEEDBACK_LOG.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except:
                continue
            action = entry.get("action", "unknown")
            rating = entry.get("rating")
            note = entry.get("note")
            if rating == "up":
                ACTION_SCORES[action]["up"] += 1
            elif rating == "down":
                ACTION_SCORES[action]["down"] += 1
                if note:
                    ACTION_NOTES[action].append(note)
            else:
                ACTION_SCORES[action]["null"] += 1

def score_for(action):
    s = ACTION_SCORES[action]
    return s["up"] - s["down"]

def generate_rules():
    positive = []
    negative = []
    neutral = []
    for action, scores in ACTION_SCORES.items():
        s = score_for(action)
        notes = ACTION_NOTES[action]
        total = scores["up"] + scores["down"]
        if total == 0:
            continue
        entry = f"- `{action}`: score {s:+d} ({scores['up']}👍 {scores['down']}👎)"
        if notes:
            reasons = "; ".join(f'"{n}"' for n in notes[:3])
            entry += f"\n  Notas: {reasons}"
        if s > 0:
            positive.append(entry)
        elif s < 0:
            negative.append(entry)
        else:
            neutral.append(entry)
    return positive, negative, neutral

def write_rules(positive, negative, neutral):
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        "# Learned Rules — Livy Memory Agent",
        "",
        f"Gerado por: learn_from_feedback.py",
        f"Atualizado: {today}",
        "",
        "## Regras com score positivo (manter padrão)",
    ]
    if positive:
        lines.extend(positive)
    else:
        lines.append("_Nenhuma regra aprendida ainda._")
    lines.extend(["", "## Regras com score negativo (evitar)"])
    if negative:
        lines.extend(negative)
    else:
        lines.append("_Nenhuma regra aprendida ainda._")
    lines.extend(["", "## Regras neutras (experimentar aborduras alternativas)"])
    if neutral:
        lines.extend(neutral)
    else:
        lines.append("_Nenhuma regra aprendida ainda._")
    lines.extend(["", "---", f"_score = thumbs_up - thumbs_down por tipo de ação_", ""])
    LEARNED_RULES.write_text("\n".join(lines))

def main():
    load_feedback()
    if not ACTION_SCORES:
        print("Nenhum feedback para processar.")
        return
    positive, negative, neutral = generate_rules()
    write_rules(positive, negative, neutral)
    print(f"Regras geradas: {len(positive)} positivas, {len(negative)} negativas, {len(neutral)} neutras")

if __name__ == "__main__":
    main()
```

- [ ] **Step 1: Criar esqueleto do script**
- [ ] **Step 2: Implementar load_feedback() — parsing JSONL**
- [ ] **Step 3: Implementar generate_rules() e write_rules()**
- [ ] **Step 4: Testar com python3 learn_from_feedback.py (sem dados)**
- [ ] **Step 5: Commit**

---

## Task 5: feedback_poller.py

**Files:**
- Create: `handlers/feedback_poller.py`

**Resumo:** Daemon leve que faz polling no Telegram API para receber callbacks dos botões 👍/👎. Roda via cron a cada 1 minuto. Grava ratings no feedback-log.jsonl.

**Importante:** O polling usa a Telegram Bot API diretamente via requests. O bot token está no openclaw.json (`8738927361:AAFIG5E9-ND9hwb2onxbLLBi03aQZzofuoE`). Filtra callbacks do DM com Lincoln (user ID `7426291192`) — não do grupo.

**Dependência:** `requests` (já disponível no sistema ou instalar via pip).

```python
#!/usr/bin/env python3
"""
Feedback Poller — polling Telegram para callback queries dos botões 👍/👎.

Uso (cron a cada 1 min):
  python3 handlers/feedback_poller.py

O poller mantém um arquivo de estado com o último update_id processado
para não processar callbacks antigos.
"""

import json, sys, time, os, signal
from pathlib import Path
from datetime import datetime

# Config — tokens e IDs
BOT_TOKEN = "8738927361:AAFIG5E9-ND9hwb2onxbLLBi03aQZzofuoE"
GROUP_ID = -5158607302
STATE_FILE = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/.feedback_poller_state")
FEEDBACK_LOG = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/feedback-log.jsonl")
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

import requests

def get_state():
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"last_update_id": 0}

def save_state(state):
    STATE_FILE.write_text(json.dumps(state))

def log_feedback(action, target, rating, note=None):
    entry = {
        "ts": datetime.utcnow().isoformat() + "Z",
        "action": action,
        "target": target,
        "rating": rating,
        "note": note,
    }
    with FEEDBACK_LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def parse_callback_data(data):
    """
    Parses callback_data from Telegram inline button.
    Formato esperado: "action:TARGET"  ex: "add_frontmatter:forge-platform.md"
    Retorna (action, target) ou None.
    """
    if not data:
        return None, None
    parts = data.split(":", 1)
    if len(parts) != 2:
        return None, None
    return parts[0], parts[1]

def poll():
    state = get_state()
    last_update_id = state["last_update_id"]
    url = f"{BASE_URL}/getUpdates"
    params = {"timeout": 5, "offset": last_update_id + 1, "limit": 10}
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        updates = resp.json().get("result", [])
    except Exception as e:
        print(f"Erro ao buscar updates: {e}", flush=True)
        return

    for update in updates:
        update_id = update.get("update_id", 0)
        callback = update.get("callback_query", {})
        if not callback:
            continue
        # garantir que só processa callbacks do DM com Lincoln
        user = callback.get("from", {})
        if user.get("id") != 7426291192:
            continue
        data = callback.get("data", "")
        action, target = parse_callback_data(data)
        if action is None:
            continue
        # rating: 👍 = up, 👎 = down
        # o data do botão contém o rating no formato "action:target:up" ou "action:target:down"
        parts = data.split(":")
        if len(parts) >= 3:
            rating = parts[2]  # "up" or "down"
        else:
            rating = None
        if rating in ("up", "down"):
            log_feedback(action, target, rating)
            print(f"Feedback registrado: {action} {target} {rating}", flush=True)
        # responder ao callback para remover loading state
        callback_id = callback.get("id")
        if callback_id:
            requests.post(f"{BASE_URL}/answerCallbackQuery",
                         json={"callback_query_id": callback_id})
        # atualizar last_update_id
        if update_id > last_update_id:
            last_update_id = update_id

    save_state({"last_update_id": last_update_id})

def main():
    # Rode uma vez e saia (cron-friendly)
    poll()

if __name__ == "__main__":
    main()
```

- [ ] **Step 1: Criar handlers/ directory**
- [ ] **Step 2: Implementar esqueleto com config e parse_callback_data()**
- [ ] **Step 3: Implementar poll() com Telegram getUpdates API**
- [ ] **Step 4: Implementar log_feedback() e main()**
- [ ] **Step 5: Testar python3 handlers/feedback_poller.py (sem effects se não houver callbacks)**
- [ ] **Step 6: Commit**

---

## Task 6: Cron — autoresearch-hourly

**Resumo:** Configurar cron job no OpenClaw para rodar de 1 em 1 hora.

**Ação:** O cron executa o agente `memory-agent` com prompt que:
1. Lê métricas atuais (autoresearch_metrics.py)
2. Se score < threshold, executa /autoresearch com as ações apropriadas
3. Envia cada ação ao Telegram grupo `-5158607302` com inline buttons
4. Para cada ação, o botão 👍 → callback "action:target:up", 👎 → "action:target:down"

**Nota sobre o cron:** O cron existente `dream-memory-consolidation` (ff61a80c...) roda às 07h. Precisamos de um cron adicional `autoresearch-hourly` rodando a cada 1h.

```bash
# Criar o cron via OpenClaw CLI
openclaw cron add \
  --name "autoresearch-hourly" \
  --at "0 * * * *" \
  --message "autoresearch-memory" \
  --target isolated \
  --agent memory-agent
```

O prompt da mensagem do cron (armazenado no cron config) deve conter as instruções completas para o agente.

- [ ] **Step 1: Criar cron job via openclaw cli**
- [ ] **Step 2: Verificar que o cron aparece em openclaw cron list**
- [ ] **Step 3: Commit**

---

## Task 7: Cron — feedback-poller (1 min)

**Resumo:** Cron job para rodar o feedback_poller.py a cada 1 minuto.

```bash
openclaw cron add \
  --name "feedback-poller" \
  --at "* * * * *" \
  --message "python3 handlers/feedback_poller.py" \
  --target isolated \
  --agent -
```

- [ ] **Step 1: Criar cron job de polling via openclaw cli**
- [ ] **Step 2: Commit**

---

## Task 8: Integrar Learn ao Cron de Learn

**Resumo:** Cron `memory-feedback-learn` (23h BRT) que roda learn_from_feedback.py diariamente.

```bash
openclaw cron add \
  --name "memory-feedback-learn" \
  --at "0 23 * * *" \
  --message "python3 skills/memoria-consolidation/learn_from_feedback.py" \
  --target isolated \
  --agent memory-agent
```

- [ ] **Step 1: Criar cron de learn diario**
- [ ] **Step 2: Commit**

---

## Task 9: Teste de Integração Completa

**Resumo:** Testar o sistema completo: métricas → ação → Telegram → feedback → learned rules.

**Teste manual:**
1. `python3 skills/memoria-consolidation/autoresearch_metrics.py --all` → verifica métricas
2. Criar um topic file de teste com frontmatter incompleto
3. `python3 skills/memoria-consolidation/autoresearch_verify.py --metric completeness` → score atual
4. Adicionar manualmente uma entrada de feedback no feedback-log.jsonl
5. `python3 learn_from_feedback.py` → verifica learned-rules.md gerado
6. `python3 handlers/feedback_poller.py` → verifica que não quebra

- [ ] **Step 1: Criar topic file de teste em memory/curated/test-topic.md com frontmatter parcial**
- [ ] **Step 2: Rodar métricas e verificar output**
- [ ] **Step 3: Adicionar entrada de feedback manual no feedback-log.jsonl**
- [ ] **Step 4: Rodar learn_from_feedback.py e verificar learned-rules.md**
- [ ] **Step 5: Commit**

---

## Ordem de Execução

1. Task 3 (feedback-log + learned-rules template) — dependência base
2. Task 1 (autoresearch_metrics.py) — dependência para Task 2
3. Task 2 (autoresearch_verify.py) — usa metrics
4. Task 4 (learn_from_feedback.py) — usa feedback-log
5. Task 5 (feedback_poller.py) —polling Telegram
6. Task 6 (cron autoresearch-hourly)
7. Task 7 (cron feedback-poller 1min)
8. Task 8 (cron memory-feedback-learn)
9. Task 9 (teste de integração)
