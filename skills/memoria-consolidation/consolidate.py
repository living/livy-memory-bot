#!/usr/bin/env python3
"""
Auto Dream Adaptado — Consolidação de Memória Living

4 fases:
  1. Orientation — escanear MEMORY.md + topic files
  2. Gather Signal — detectar relative dates, stale, contradictions
  3. Consolidation — converter datas, arquivar stale, resolver conflitos
  4. Prune & Index — reescrever MEMORY.md, gerar consolidation-log.md

RESILIÊNCIA:
- Lock file impede execuções concorrentes
- Dry-run antes de aplicar (não há rollback para renames)
- Per-file try/except impede que erro em um arquivo pare o script
- Validação inline: falha se MEMORY.md > 200 linhas após consolidação
- Duplo threshold: >60d archiva, 30-60d monitora, <30d ignora
"""

import os, re, json, sys
from datetime import datetime
from pathlib import Path

MEMORY_DIR  = Path("/home/lincoln/.openclaw/workspace/memory")
ARCHIVE_DIR = MEMORY_DIR / ".archive"
MEMORY_INDEX = MEMORY_DIR.parent / "MEMORY.md"
LOG_FILE   = MEMORY_DIR / "consolidation-log.md"
LOCK_FILE  = MEMORY_DIR / ".consolidation.lock"

def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}", flush=True)

def fail(msg):
    log(msg, "ERROR")
    sys.exit(1)

# ── LOCK FILE (concurrency guard) ──────────────────────────────────────────

def acquire_lock():
    """Cria lock file com PID. Falha se já existir."""
    if LOCK_FILE.exists():
        old_pid = LOCK_FILE.read_text().strip()
        if old_pid.isdigit() and os.path.exists(f"/proc/{old_pid}"):
            fail(f"Consolidação já em execução (PID {old_pid}). Abortando.")
        log(f"Lock file stale (PID {old_pid}). Removendo.")
        LOCK_FILE.unlink()
    LOCK_FILE.write_text(str(os.getpid()))
    log(f"Lock adquirido (PID {os.getpid()})")

def release_lock():
    if LOCK_FILE.exists():
        LOCK_FILE.unlink()
        log("Lock released")

# ── PHASE 1: ORIENTATION ──────────────────────────────────────────────────

def load_memory_index():
    """Lê MEMORY.md e extrai topic files referenciados."""
    if not MEMORY_INDEX.exists():
        return "", set()
    content = MEMORY_INDEX.read_text()
    refs = re.findall(r'\[([^\]]+)\]\(memory/([^\)]+)\)', content)
    referenced = {r[1] for r in refs}
    return content, referenced

# ── PHASE 2: GATHER SIGNAL ───────────────────────────────────────────────

def gather_signal(referenced_topic_files):
    """
    Coleta sinais em curated/*.md e topic files level-root.

    Lógica orphan: APENAS curated/*.md são topic files.
    daily logs (YYYY-MM-DD*.md) nunca são orphans.
    consolidation-log.md é excluído (não é topic file).
    """
    curated_files = list((MEMORY_DIR / "curated").glob("*.md")) \
        if (MEMORY_DIR / "curated").exists() else []
    top_level = [
        f for f in MEMORY_DIR.glob("*.md")
        if f.name not in ("heartbeat-state.json",
                          "consolidation-log.md",
                          ".consolidation.lock")
        and not f.name.startswith(".")
        and f.name not in [p.name for p in curated_files]
    ]
    all_topic_files = set(f.name for f in curated_files + top_level)

    orphaned = list(all_topic_files - referenced_topic_files)

    signals = {
        "relative_dates": [],
        "stale":          [],
        "orphaned":       orphaned,
        "multi_date":     [],
    }

    for f in curated_files + top_level:
        try:
            content = f.read_text()
        except Exception as e:
            log(f"  Erro lendo {f.name}: {e}", "WARN")
            continue

        # Relative dates
        for pattern, label in [
            (r"\bontem\b",      "ontem"),
            (r"\banteontem\b",  "anteontem"),
            (r"\bhá (\d+) dias\b", "há X dias"),
        ]:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if len(matches) > 1:
                signals["multi_date"].append((f.name, len(matches), label))
            elif len(matches) == 1:
                signals["relative_dates"].append((f.name, label, pattern))

        # Stale
        for ind in ["TODO", "TODO:", "FIXME", "pendente", "bug", "em andamento"]:
            if ind.lower() in content.lower():
                signals["stale"].append((f.name, ind))
                break

    return signals

# ── PHASE 3: CONSOLIDATION ───────────────────────────────────────────────

def consolidate(signals, dry_run=True):
    """
    Dry-run primeiro, depois apply.
    Renames não são atômicos entre diretórios — por isso o 2-pass.
    """
    changes  = []
    staged   = []

    for fname, label, pattern in signals["relative_dates"]:
        fpath = MEMORY_DIR / fname
        if not fpath.exists():
            continue
        date_match = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
        file_date = date_match.group(1) if date_match else "data-desconhecida"
        try:
            content = fpath.read_text()
            new_content = re.sub(pattern, file_date, content,
                                 count=1, flags=re.IGNORECASE)
            if new_content != content:
                changes.append(f"  - {fname}: '{label}' → '{file_date}'")
                staged.append((fpath, new_content, "replace"))
        except Exception as e:
            log(f"  Erro processando {fname}: {e}", "WARN")

    for fname, count, label in signals["multi_date"]:
        log(f"  ⚠️ {fname}: {count}x '{label}' — requer revisão manual", "WARN")
        changes.append(f"  - ⚠️ {fname}: {count}x '{label}' — requer revisão manual")

    # Duplo threshold: >60d archiva, 30-60d monitora, <30d ignora
    cutoff_30 = datetime.now().timestamp() - 30 * 86400
    cutoff_60 = datetime.now().timestamp() - 60 * 86400

    for fname, indicator in signals["stale"]:
        fpath = MEMORY_DIR / fname
        if not fpath.exists():
            continue
        mtime = fpath.stat().st_mtime
        if mtime < cutoff_60:
            ARCHIVE_DIR.mkdir(exist_ok=True)
            dst = ARCHIVE_DIR / f"{fname.replace('.md','')}-stale.md"
            changes.append(f"  - {fname} → .archive/ (stale:{indicator}, >60d)")
            staged.append((fpath, dst, "rename"))
        elif mtime < cutoff_30:
            changes.append(f"  - {fname}: stale:{indicator} (30-60d) — monitorar")

    if not dry_run:
        for item in staged:
            if item[2] == "replace":
                item[0].write_text(item[1])
            elif item[2] == "rename":
                item[0].rename(item[1])

    return changes

# ── PHASE 4: PRUNE & INDEX ───────────────────────────────────────────────

def prune_and_index(changes, dry_run=True):
    """Gera consolidation-log.md e valida MEMORY.md <200 linhas."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M BRT")
    log_lines = [
        f"# Consolidation Log — {timestamp}",
        "",
        f"**Dry run:** {'Yes' if dry_run else 'No'}",
        "",
    ]
    if changes:
        log_lines.append("## Mudanças aplicadas/propostas")
        log_lines.extend(changes)
    else:
        log_lines.append("Nenhuma mudança necessária.")
    log_lines.append("")
    log_lines.append(f"**Total:** {len(changes)} mudanças")

    if not dry_run:
        LOG_FILE.write_text("\n".join(log_lines))
        log(f"Log gerado em {LOG_FILE}")

    if MEMORY_INDEX.exists():
        lines = MEMORY_INDEX.read_text().split("\n")
        status = "✅" if len(lines) <= 200 else "❌ EXCEEDED"
        log(f"MEMORY.md: {len(lines)} linhas {status}")
        if len(lines) > 200 and not dry_run:
            fail(f"MEMORY.md tem {len(lines)} linhas (>200). Corrigir.")
    else:
        log("MEMORY.md não existe — pulando validação", "WARN")

    return len(changes)

# ── MAIN ─────────────────────────────────────────────────────────────────

def main():
    log("=== Auto Dream Adaptado — Starting ===")
    acquire_lock()
    try:
        log("Fase 1: Orientation")
        content, referenced = load_memory_index()
        log(f"  MEMORY.md lido, {len(referenced)} topic files referenciados")

        log("Fase 2: Gather Signal")
        signals = gather_signal(referenced)
        log(f"  relative_dates: {len(signals['relative_dates'])}")
        log(f"  stale: {len(signals['stale'])}")
        log(f"  orphaned: {len(signals['orphaned'])}")
        log(f"  multi_date warnings: {len(signals['multi_date'])}")

        log("Fase 3: Consolidation (DRY RUN)")
        changes = consolidate(signals, dry_run=True)
        log(f"  {len(changes)} mudanças pendentes")

        log("Fase 4: Prune & Index (DRY RUN)")
        prune_and_index(changes, dry_run=True)

        if changes:
            log("=== DRY RUN CONCLUÍDO — aplicando ===")
            changes = consolidate(signals, dry_run=False)
            prune_and_index(changes, dry_run=False)
        else:
            log("=== Nenhuma mudança necessária ===")

    finally:
        release_lock()

if __name__ == "__main__":
    main()
