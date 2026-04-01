#!/usr/bin/env python3
"""
Autoresearch Cron Wrapper — sends results via Telegram API (bot 8725269523)

1. Run autoresearch metrics + consolidation
2. Send each modified file as document attachment
3. Send summary with 👍/👎 feedback buttons
4. Feedback callbacks go to webhook handler on port 8080
"""

import ast
import json, os, subprocess, sys, requests
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
BOT_TOKEN = "8725269523:AAFqAFEFcbAa6daClbUiVH9qBLfzu46SMOQ"
BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
USER_ID = 7426291192  # Lincoln
CHAT_ID = USER_ID     # DM to Lincoln

WORKSPACE = Path("/home/lincoln/.openclaw/workspace-livy-memory")
MEMORY_DIR = WORKSPACE / "memory"
CURATED_DIR = MEMORY_DIR / "curated"

# ── Helpers ──────────────────────────────────────────────────────────────────

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def health_check():
    """
    Verifies all 3 memory layers are available.
    Returns True if all up, False if any down.
    Aborts the entire cycle if any layer is down.
    """
    errors = []

    # Layer 1: openclaw memory
    try:
        r = subprocess.run(
            ["openclaw", "memory", "status"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode != 0:
            errors.append("openclaw memory: unreachable")
    except Exception as e:
        errors.append(f"openclaw memory: {e}")

    # Layer 2: claude-mem worker
    try:
        resp = requests.get("http://localhost:37777/api/health", timeout=5)
        if resp.status_code != 200 or resp.json().get("status") != "ok":
            errors.append("claude-mem worker: unhealthy")
    except Exception:
        errors.append("claude-mem worker: unreachable")

    # Layer 3: curated dir
    if not CURATED_DIR.exists():
        errors.append("curated dir: not found")

    if errors:
        log(f"HEALTH CHECK FAILED: {'; '.join(errors)}. Abortando.")
        return False
    log("Health check: OK (3/3 layers)")
    return True

def send_document(chat_id, file_path, caption=None):
    """Send a document via Telegram Bot API (no buttons in caption)."""
    url = f"{BASE_URL}/sendDocument"
    with open(file_path, "rb") as f:
        data = {"chat_id": chat_id}
        if caption:
            data["caption"] = caption
        files = {"document": (file_path.name, f)}
        resp = requests.post(url, data=data, files=files, timeout=30)
        result = resp.json()
        if not result.get("ok"):
            log(f"  ⚠️ sendDocument failed: {result.get('description', result)}")
        return result.get("ok")

def summarize_file(file_path, max_lines=7):
    """Gera resumo do arquivo (primeiras linhas / frontmatter)."""
    try:
        content = file_path.read_text()
        lines = content.split("\n")[:max_lines]
        summary_lines = []
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#+"):
                continue
            summary_lines.append(line)
            if len(summary_lines) >= 5:
                break
        summary = " | ".join(summary_lines[:5])
        if len(summary) > 150:
            summary = summary[:147] + "..."
        return summary if summary else "arquivo de memória"
    except:
        return "arquivo de memória"

def send_message(chat_id, text, reply_markup=None):
    """Send a text message via Telegram Bot API."""
    url = f"{BASE_URL}/sendMessage"
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
    }
    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)
    resp = requests.post(url, json=data, timeout=10)
    result = resp.json()
    if not result.get("ok"):
        log(f"  ⚠️ sendMessage failed: {result.get('description', result)}")
    return result.get("ok")

def feedback_buttons(sep, filename):
    """Inline keyboard with 👍/👎 for feedback. Uses | as sep to avoid filename issues."""
    return {
        "inline_keyboard": [[
            {"text": "👍", "callback_data": f"feedback|{sep}|{filename}|up"},
            {"text": "👎", "callback_data": f"feedback|{sep}|{filename}|down"},
        ]]
    }

def read_learned_rules():
    """Lê learned-rules.md e retorna regras de feedback."""
    rules_path = MEMORY_DIR / "learned-rules.md"
    if not rules_path.exists():
        return {}
    try:
        content = rules_path.read_text()
        rules = {"positive": [], "negative": [], "neutral": []}
        current_section = None
        for line in content.split("\n"):
            if "score positivo" in line:
                current_section = "positive"
            elif "score negativo" in line:
                current_section = "negative"
            elif "score 0" in line or "neutras" in line:
                current_section = "neutral"
            elif current_section and line.strip().startswith("- `") and "`" in line:
                # Extract action name and note
                action = line.split("`")[1] if "`" in line else ""
                note = ""
                if "Notas:" in line:
                    note = line.split("Notas:")[1].strip()
                if action:
                    rules[current_section].append({"action": action, "note": note})
        return rules
    except Exception as e:
        log(f"⚠️ Failed to read learned-rules: {e}")
        return {}

def search_memory_context(query, max_results=3):
    """Busca contexto relevante via openclaw memory search."""
    try:
        result = subprocess.run(
            ["openclaw", "memory", "search", "--max-results", str(max_results), "--json", query],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return json.loads(result.stdout.strip())
    except Exception as e:
        log(f"⚠️ Memory search failed: {e}")
    return []

def get_context_for_file(file_path):
    """Busca contexto relevante para um arquivo."""
    # Remove .md extension for cleaner search
    query_base = file_path.stem.replace("-", " ").replace("_", " ")
    results = search_memory_context(query_base, max_results=2)
    rules = read_learned_rules()

    context_parts = []

    # Add rule feedback for this file
    filename = file_path.name
    for section, rule_list in [("positive", rules.get("positive", [])), ("negative", rules.get("negative", []))]:
        for rule in rule_list:
            if filename in rule.get("action", "") or rule.get("action", "").endswith(filename):
                if rule.get("note"):
                    context_parts.append(f"[{section.upper()}] {rule['note']}")

    # Add memory search context
    if results and isinstance(results, list):
        for r in results[:2]:
            if isinstance(r, dict) and r.get("text"):
                # Truncate long context
                text = r["text"][:200] + "..." if len(r.get("text", "")) > 200 else r.get("text", "")
                context_parts.append(f"[MEMORY] {text}")

    return " | ".join(context_parts) if context_parts else None

# ── Metrics ─────────────────────────────────────────────────────────────────

def run_metrics():
    """Run autoresearch_metrics.py and return results."""
    log("Running metrics...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "skills/memoria-consolidation/autoresearch_metrics.py"), "--all"],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    if result.returncode != 0:
        log(f"⚠️ metrics failed: {result.stderr}")
        return None
    try:
        return json.loads(result.stdout.strip())
    except:
        try:
            # Fallback: Python dict format
            return ast.literal_eval(result.stdout.strip())
        except:
            log(f"⚠️ metrics parse error: {result.stdout}")
            return None

# ── Consolidation ─────────────────────────────────────────────────────────────

def run_consolidation():
    """Run consolidate.py (dry-run first, apply if changes)."""
    log("Running consolidation (Mente Coletiva)...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "skills/memoria-consolidation/consolidate.py")],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    log(result.stdout)
    if result.returncode != 0:
        log(f"⚠️ consolidation failed: {result.stderr}")
    return result.returncode == 0

# ── Dream (Sessions) ──────────────────────────────────────────────────────────

def run_dream():
    """Run dream_all.py to process sessions."""
    log("Running dream (sessions do main)...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "skills/memoria-consolidation/dream_all.py")],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    if result.returncode != 0:
        log(f"⚠️ dream failed: {result.stderr}")
    return result.returncode == 0

# ── Get modified files ──────────────────────────────────────────────────────────

def get_curated_files():
    """List all curated markdown files."""
    if not CURATED_DIR.exists():
        return []
    return sorted(CURATED_DIR.glob("*.md"))

# ── Evolution Cursor (round-robin) ────────────────────────────────────────────

CURSOR_FILE = MEMORY_DIR / ".evolution_cursor"
MAX_FILES_PER_CYCLE = 5

def load_cursor() -> int:
    """Load last processed cursor index. Returns 0 if file missing."""
    if not CURSOR_FILE.exists():
        return 0
    try:
        return int(CURSOR_FILE.read_text().strip())
    except Exception:
        return 0

def save_cursor(idx: int):
    """Persist cursor index to disk."""
    CURSOR_FILE.write_text(str(idx))

# ── Evolution Prompt Builder ─────────────────────────────────────────────────

def build_evolution_prompt(file_path: Path, violations: list) -> str:
    """Build the prompt sent to livy-memory agent for one file."""
    try:
        content = file_path.read_text()[:2000]
    except Exception:
        content = "(unable to read file)"

    theme = file_path.stem.replace("-", " ").replace("_", " ")

    return f"""Você é o agente de consolidação da memória institucional.

TAREFA: Reescreva o arquivo {file_path} segundo o memory-manual.md.

ANTES de reescrever, pesquise em todas as 3 camadas para enriquecer o conteúdo:

1. CAMADA 1 (Built-in search):
   Execute: openclaw memory search --json "{theme}"
   Leia os resultados mais relevantes

2. CAMADA 2 (claude-mem observations):
   Execute: curl "http://localhost:37777/api/search?query={theme}&limit=5"
   Se IDs relevantes forem encontrados:
   - Execute: curl "http://localhost:37777/api/timeline?anchor=<id>&depth_before=2&depth_after=2"
   - Execute: curl -X POST "http://localhost:37777/api/observations/batch" \\
     -H "Content-Type: application/json" \\
     -d '{{"ids": [<ids relevantes>],"orderBy":"date_desc"}}'

3. CAMADA 3 (curated files):
   Leia MEMORY.md e arquivos relacionados em memory/curated/

VIOLAÇÕES DETECTADAS:
{', '.join(violations)}

REGRAS (memory-manual.md):
- YAML frontmatter com name, description, type
- Seções: Status, Decisões (com MOTIVO da escolha), Pendências, Bugs
- Status: ativo | pausado | concluído | cancelado
- NUNCA remova conteúdo existente — só reestruture e enriqueça
- Seções Decisões devem explicar o PORQUE de cada decisão

PASSOS OBRIGATÓRIOS:
1. Execute as pesquisas nas 3 camadas
2. Leia memory-manual.md para entender o formato ideal
3. ARQUIVE a versão original ANTES de qualquer modificação:
   mkdir -p .archive/$(date +%Y%m%d%H%M)
   cp {file_path} .archive/$(date +%Y%m%d%H%M)/
4. Reescreva o arquivo integrando o contexto das 3 camadas
5. Retorne um relatório breve do que mudou e por quê

ARQUIVO ATUAL (primeiros 2000 chars):
{content}
"""

# ── Evolution Runner ──────────────────────────────────────────────────────────

def run_memory_evolution():
    """
    Detects violations, selects top 5 (round-robin), and delegates
    each to the livy-memory agent for research + rewrite.
    Returns list of (filename, report, violations) tuples.
    """
    from consolidate import detect_violations, gather_signal_all, load_memory_indexes

    log("Running memory evolution...")

    indexes = load_memory_indexes()
    signals = gather_signal_all(indexes)

    curated_files = get_curated_files()
    if not curated_files:
        log("No curated files found.")
        return []

    violations = detect_violations(curated_files, signals)
    if not violations:
        log("No violations detected.")
        return []

    cursor = load_cursor()
    total = len(violations)
    selected = []
    for i in range(MAX_FILES_PER_CYCLE):
        idx = (cursor + i) % total
        selected.append(violations[idx])

    next_cursor = (cursor + MAX_FILES_PER_CYCLE) % total
    save_cursor(next_cursor)

    log(f"Selected {len(selected)} files for evolution: {[v['file'].name for v in selected]}")

    reports = []
    for v in selected:
        f = v["file"]
        prompt = build_evolution_prompt(f, v["violations"])
        log(f"Delegating to livy-memory: {f.name}")

        try:
            result = subprocess.run(
                ["openclaw", "agent", "--agent", "livy-memory", "--message", prompt],
                capture_output=True, text=True, timeout=120
            )
            report = result.stdout.strip() if result.stdout else "(no output)"
            if result.returncode != 0:
                report = f"ERROR (rc={result.returncode}): {result.stderr.strip()}"
            log(f"  → {report[:200]}")
        except subprocess.TimeoutExpired:
            report = "TIMEOUT — agent did not complete within 120s"
            log(f"  → TIMEOUT for {f.name}")
        except Exception as e:
            report = f"EXCEPTION: {e}"
            log(f"  → EXCEPTION for {f.name}: {e}")

        reports.append((f.name, report, v["violations"]))

    return reports

# ── Main ─────────────────────────────────────────────────────────────────────

# ── Feedback Learning ─────────────────────────────────────────────────────────────

def run_feedback_learning():
    """Lê feedback acumulado e atualiza learned-rules.md."""
    log("Processing accumulated feedback...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "skills/memoria-consolidation/learn_from_feedback.py")],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    if result.returncode == 0:
        log(result.stdout.strip())
    else:
        log(f"Feedback learning: {result.stderr.strip() or 'no feedback yet'}")
    return result.returncode == 0

def run_meetings_tldv_autoresearch():
    """Run meetings_tldv daily autoresearch."""
    log("Running meetings-tldv autoresearch...")
    result = subprocess.run(
        ["python3", str(WORKSPACE / "scripts/meetings_tldv_autoresearch.py")],
        capture_output=True, text=True, cwd=str(WORKSPACE)
    )
    if result.returncode == 0:
        log(result.stdout.strip())
    else:
        log(f"meetings-tldv autoresearch: {result.stderr.strip() or 'no feedback yet'}")
    return result.returncode == 0

def main():
    log("=== Autoresearch Cron (Telegram Direct) ===")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M BRT")

    # 0. Health check — abort if any layer is down
    if not health_check():
        summary = f"""🧠 *Autoresearch — {timestamp}*

⚠️ *Ciclo abortado — dependência down.*

🔄 Próximo ciclo em ~1h. Nenhuma evolução aplicada."""
        send_message(CHAT_ID, summary)
        sys.exit(1)

    # 0b. Process feedback acumulado desde última execução
    run_feedback_learning()

    # 1. Run metrics before
    metrics_before = run_metrics()
    log(f"Metrics before: {metrics_before}")

    # 2. Run consolidation (Mente Coletiva)
    consolidation_ok = run_consolidation()

    # 3. Run dream (processa sessões do main)
    dream_ok = run_dream()

    # 3b. Run meetings-tldv autoresearch
    meetings_tldv_ok = run_meetings_tldv_autoresearch()

    # 4. Run memory evolution (top 5 files, round-robin)
    evolution_reports = run_memory_evolution()
    evolution_count = len([r for r in evolution_reports if not r[1].startswith("ERROR")])

    # 5. Run metrics after
    metrics_after = run_metrics()
    log(f"Metrics after: {metrics_after}")

    # 4. Get files to send
    files = get_curated_files()
    log(f"Found {len(files)} curated files")

    # 5. Send intro message with file list and feedback buttons for each
    action_id = datetime.now().strftime("%Y%m%d%H%M")

    # Build buttons for each file
    file_buttons = []
    for f in files:
        file_buttons.append({"text": f"📄 {f.name}", "callback_data": f"view:{action_id}:{f.name}"})

    intro_keyboard = {
        "inline_keyboard": [
            [{"text": "👍 Tudo ok", "callback_data": f"feedback|{action_id}|all|up"},
             {"text": "👎 Precisa melhorar", "callback_data": f"feedback|{action_id}|all|down"}],
        ]
    }

    # Build evolution section
    if evolution_reports:
        evolution_lines = ["🔄 *Evoluções aplicadas:*"]
        for fname, report, violations in evolution_reports:
            short_violations = ", ".join(violations[:2])
            if report.startswith("ERROR") or report.startswith("TIMEOUT") or report.startswith("EXCEPTION"):
                evolution_lines.append(f"• `{fname}` — ❌ {report[:80]}")
            else:
                evolution_lines.append(f"• `{fname}` — ✅ {short_violations}")
        evolution_summary = "\n".join(evolution_lines)
        evolution_summary += f"\n📋 *Evoluções: {evolution_count}/{len(evolution_reports)} aplicadas*"
    else:
        evolution_summary = "✅ *Nenhuma violação detectada — nenhuma evolução necessária.*"

    intro = f"""🧠 *Autoresearch — {timestamp}*

📊 *Métricas:* completeness {metrics_before.get('completeness',0):.1f} → {metrics_after.get('completeness',0):.1f} | crossrefs {metrics_before.get('crossrefs',0)} → {metrics_after.get('crossrefs',0)}

{evolution_summary}

📁 *{len(files)} arquivos para revisar:*"""

    send_message(CHAT_ID, intro, reply_markup=intro_keyboard)

    # 6. Send each file as document (no buttons) + summary message with buttons
    sent_files = []
    for f in files:
        log(f"Sending {f.name}...")
        # Message 1: document only
        ok = send_document(
            CHAT_ID, f,
            caption=f"📄 {f.name}"
        )
        if ok:
            sent_files.append(f.name)
            # Message 2: summary + feedback + context + buttons
            summary = summarize_file(f)
            context = get_context_for_file(f)
            msg = f"Resumo: {summary}"
            if context:
                msg += f"\n\n💡 {context}"
            msg += "\n\n"
            send_message(
                CHAT_ID, msg,
                reply_markup=feedback_buttons(action_id, f.name)
            )

    # 7. Send summary with feedback button
    if metrics_before and metrics_after:
        delta_completeness = metrics_after.get("completeness", 0) - metrics_before.get("completeness", 0)
        delta_crossrefs = metrics_after.get("crossrefs", 0) - metrics_before.get("crossrefs", 0)

        summary = f"""📋 *Resumo:*
• completeness: {metrics_before.get('completeness',0):.1f} → {metrics_after.get('completeness',0):.1f} {'✅' if delta_completeness >= 0 else '❌'}
• crossrefs: {metrics_before.get('crossrefs',0)} → {metrics_after.get('crossrefs',0)} {'✅' if delta_crossrefs >= 0 else '❌'}
• actions: {metrics_after.get('actions',0)}

Clique nos botões acima para avaliar."""

        if consolidation_ok:
            summary += f"\n\n✅ Consolidation completed."
    else:
        summary = f"⚠️ Metrics unavailable."

    ok = send_message(
        CHAT_ID, summary,
        reply_markup=feedback_buttons(action_id, "summary")
    )

    if ok:
        log("=== Autoresearch Cron COMPLETE ===")
    else:
        log("⚠️ Summary send failed")
        sys.exit(1)

if __name__ == "__main__":
    main()
