#!/usr/bin/env python3
"""
Auto Dream Adaptado — Consolidação de Memória (workspace-livy-memory)

Este script consolida TODAS as memórias da Living num único fluxo:
1. Memória do memory-agent: workspace-livy-memory/memory/
2. Memória do main (Livy Deep): workspace/memory/

A memória é uma mente coletiva — o memory-agent curatea tudo.

4 fases:
  1. Orientation — escanear índices + topic files de TODOS
  2. Gather Signal — detectar relative dates, stale, contradictions
  3. Consolidation — converter datas, arquivar stale, resolver conflitos
  4. Prune & Index — reescrever índices, gerar consolidation-log.md

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

# ── Mente Coletiva — TODAS as memórias ────────────────────────────────────────
MEMORY_SPACES = [
    {
        "name": "memory-agent",
        "memory_dir": Path("/home/lincoln/.openclaw/workspace-livy-memory/memory"),
        "index_file": Path("/home/lincoln/.openclaw/workspace-livy-memory/MEMORY.md"),
        "curated_dir": Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/curated"),
    },
    {
        "name": "main (Livy Deep)",
        "memory_dir": Path("/home/lincoln/.openclaw/workspace/memory"),
        "index_file": Path("/home/lincoln/.openclaw/workspace/MEMORY.md"),
        "curated_dir": Path("/home/lincoln/.openclaw/workspace/memory/curated"),
    },
]

ARCHIVE_DIR = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/.archive")
LOG_FILE   = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/consolidation-log.md")
LOCK_FILE  = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory/.consolidation.lock")

def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}", flush=True)

def fail(msg):
    log(msg, "ERROR")
    sys.exit(1)

# ── LOCK FILE (concurrency guard) ──────────────────────────────────────────────

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

# ── PHASE 1: ORIENTATION (TODOS OS ESPAÇOS) ──────────────────────────────────

def load_memory_indexes():
    """Lê todos os MEMORY.md e extrai topic files referenciados."""
    indexes = {}
    for space in MEMORY_SPACES:
        idx_file = space["index_file"]
        if idx_file.exists():
            content = idx_file.read_text()
            refs = re.findall(r'\[([^\]]+)\]\(memory/([^\)]+)\)', content)
            referenced = {r[1] for r in refs}
            indexes[space["name"]] = {
                "content": content,
                "referenced": referenced,
                "index_file": idx_file,
            }
        else:
            indexes[space["name"]] = {
                "content": "",
                "referenced": set(),
                "index_file": idx_file,
            }
    return indexes

# ── PHASE 2: GATHER SIGNAL (TODOS OS ESPAÇOS) ────────────────────────────────

def gather_signal_all(indexes):
    """
    Coleta sinais em TODOS os curated/*.md e topic files.
    Lógica orphan: APENAS curated/*.md são topic files.
    """
    all_signals = {}

    for space in MEMORY_SPACES:
        mem_dir = space["memory_dir"]
        curated_dir = space["curated_dir"]
        referenced = indexes.get(space["name"], {}).get("referenced", set())

        curated_files = list(curated_dir.glob("*.md")) if curated_dir.exists() else []
        top_level = [
            f for f in mem_dir.glob("*.md")
            if f.name not in ("heartbeat-state.json",
                              "consolidation-log.md",
                              ".consolidation.lock")
            and not f.name.startswith(".")
            and f.name not in [p.name for p in curated_files]
        ]

        all_topic_files = set(f.name for f in curated_files + top_level)
        orphaned = list(all_topic_files - referenced)

        signals = {
            "space": space["name"],
            "curated_dir": curated_dir,
            "memory_dir": mem_dir,
            "relative_dates": [],
            "stale": [],
            "orphaned": orphaned,
            "multi_date": [],
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

        all_signals[space["name"]] = signals

    return all_signals

# ── PHASE 2B: VIOLATION DETECTION ─────────────────────────────────────────

VIOLATION_WEIGHTS = {
    "missing-frontmatter": 8,
    "missing-status": 4,
    "missing-decisoes": 6,
    "decisoes-no-reason": 3,
    "daily-log-in-curated": 5,
    "only-description": 2,
    "stale": 10,
}

REASON_PATTERNS = re.compile(
    r'\b(porque|motivo|razão|since|because|devido|por causa)\b',
    re.IGNORECASE
)

FRONTMATTER_RE = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)
STATUS_RE = re.compile(r'^## Status|^\*\*Status:\*\*', re.MULTILINE | re.IGNORECASE)
DECISOES_RE = re.compile(r'^## Decisões|^\*\*Decisões:\*\*', re.MULTILINE | re.IGNORECASE)
DATE_LOG_RE = re.compile(r'^\d{4}-\d{2}-\d{2}')

def _has_frontmatter(content: str) -> bool:
    m = FRONTMATTER_RE.match(content)
    if not m:
        return False
    fm_text = m.group(1)
    return all(k in fm_text for k in ['name:', 'description:', 'type:'])

def _has_status(content: str) -> bool:
    """Has Status: either in frontmatter or body section."""
    m = FRONTMATTER_RE.match(content)
    if m and 'status:' in m.group(1):
        return True
    return bool(STATUS_RE.search(content))

def _has_decisoes(content: str) -> bool:
    """Has Decisões: either 'decision:' in frontmatter or ## Decisões body section."""
    m = FRONTMATTER_RE.match(content)
    if m and 'decision:' in m.group(1):
        return True
    return bool(DECISOES_RE.search(content))

def _decisoes_have_reason(content: str) -> bool:
    """Check if each decision line contains a reason pattern."""
    m = FRONTMATTER_RE.match(content)
    if m and 'decision:' in m.group(1):
        # Decision in frontmatter — check if it has a reason
        decision_line = [l for l in m.group(1).split('\n') if 'decision:' in l]
        if decision_line:
            return bool(REASON_PATTERNS.search(decision_line[0]))
        return True
    lines = content.split('\n')
    in_decisoes = False
    decision_lines = []
    for line in lines:
        if DECISOES_RE.search(line):
            in_decisoes = True
            continue
        if in_decisoes:
            if line.strip() == '' or line.startswith('#'):
                break
            if line.strip().startswith('-'):
                decision_lines.append(line)
    if not decision_lines:
        return True
    with_reason = sum(1 for l in decision_lines if REASON_PATTERNS.search(l))
    return with_reason >= len(decision_lines) / 2

def detect_violations(files: list, signals: dict) -> list:
    """
    Returns list of dicts: {file, score, violations[]}
    Only curated/*.md files are checked. Daily logs are skipped.
    """
    cutoff_60 = datetime.now().timestamp() - 60 * 86400
    results = []

    for f in files:
        try:
            content = f.read_text()
        except Exception:
            continue

        # Skip daily logs
        if DATE_LOG_RE.match(f.name):
            continue

        violations = []
        score = 0

        # Check: frontmatter
        if not _has_frontmatter(content):
            violations.append("missing-frontmatter")
            score += VIOLATION_WEIGHTS["missing-frontmatter"]

        # Check: Status section
        if not _has_status(content):
            violations.append("missing-status")
            score += VIOLATION_WEIGHTS["missing-status"]

        # Check: Decisões section
        if not _has_decisoes(content):
            violations.append("missing-decisoes")
            score += VIOLATION_WEIGHTS["missing-decisoes"]
        elif not _decisoes_have_reason(content):
            violations.append("decisoes-no-reason")
            score += VIOLATION_WEIGHTS["decisoes-no-reason"]

        # Check: stale > 60 days
        try:
            mtime = f.stat().st_mtime
            if mtime < cutoff_60:
                violations.append("stale:>60d")
                score += VIOLATION_WEIGHTS["stale"]
        except Exception:
            pass

        if violations:
            results.append({
                "file": f,
                "score": score,
                "violations": violations,
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# ── PHASE 3: CONSOLIDATION (TODOS OS ESPAÇOS) ───────────────────────────────

def consolidate_all(all_signals, dry_run=True):
    """
    Dry-run primeiro, depois apply.
    """
    changes = []
    staged = []

    for space_name, signals in all_signals.items():
        mem_dir = signals["memory_dir"]

        for fname, label, pattern in signals["relative_dates"]:
            fpath = mem_dir / fname
            if not fpath.exists():
                continue
            date_match = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
            file_date = date_match.group(1) if date_match else "data-desconhecida"
            try:
                content = fpath.read_text()
                new_content = re.sub(pattern, file_date, content,
                                     count=1, flags=re.IGNORECASE)
                if new_content != content:
                    changes.append(f"  - [{space_name}] {fname}: '{label}' → '{file_date}'")
                    staged.append((fpath, new_content, "replace"))
            except Exception as e:
                log(f"  Erro processando {fname}: {e}", "WARN")

        for fname, count, label in signals["multi_date"]:
            log(f"  ⚠️ [{space_name}] {fname}: {count}x '{label}' — requer revisão manual", "WARN")
            changes.append(f"  - ⚠️ [{space_name}] {fname}: {count}x '{label}' — requer revisão manual")

        # Duplo threshold: >60d archiva, 30-60d monitora, <30d ignora
        cutoff_30 = datetime.now().timestamp() - 30 * 86400
        cutoff_60 = datetime.now().timestamp() - 60 * 86400

        for fname, indicator in signals["stale"]:
            fpath = mem_dir / fname
            if not fpath.exists():
                continue
            mtime = fpath.stat().st_mtime
            if mtime < cutoff_60:
                ARCHIVE_DIR.mkdir(exist_ok=True)
                dst = ARCHIVE_DIR / f"{fname.replace('.md','')}-stale.md"
                changes.append(f"  - [{space_name}] {fname} → .archive/ (stale:{indicator}, >60d)")
                staged.append((fpath, dst, "rename"))
            elif mtime < cutoff_30:
                changes.append(f"  - [{space_name}] {fname}: stale:{indicator} (30-60d) — monitorar")

    if not dry_run:
        for item in staged:
            if item[2] == "replace":
                item[0].write_text(item[1])
            elif item[2] == "rename":
                item[0].rename(item[1])

    return changes

# ── PHASE 4: PRUNE & INDEX (TODOS OS ESPAÇOS) ──────────────────────────────

def prune_and_index_all(all_signals, changes, dry_run=True):
    """Gera consolidation-log.md e valida cada MEMORY.md <200 linhas."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M BRT")
    log_lines = [
        f"# Consolidation Log — {timestamp}",
        "",
        f"**Mente Coletiva:** memory-agent + Livy Deep (main)",
        f"**Dry run:** {'Yes' if dry_run else 'No'}",
        "",
    ]

    index_status = {}
    for space in MEMORY_SPACES:
        idx_file = space["index_file"]
        if idx_file.exists():
            lines = idx_file.read_text().split("\n")
            status = "✅" if len(lines) <= 200 else "❌ EXCEEDED"
            log(f"[{space['name']}] MEMORY.md: {len(lines)} linhas {status}")
            index_status[space["name"]] = len(lines)
            if len(lines) > 200 and not dry_run:
                fail(f"[{space['name']}] MEMORY.md tem {len(lines)} linhas (>200). Corrigir.")
        else:
            log(f"[{space['name']}] MEMORY.md não existe — pulando", "WARN")
            index_status[space["name"]] = 0

    if changes:
        log_lines.append("## Mudanças aplicadas/propostas")
        log_lines.extend(changes)
    else:
        log_lines.append("Nenhuma mudança necessária.")

    total_changes = len(changes)
    log_lines.append("")
    log_lines.append(f"**Total:** {total_changes} mudanças")

    # Status por espaço
    for space_name, count in index_status.items():
        log_lines.append(f"- {space_name}: {count} linhas no índice")

    if not dry_run:
        LOG_FILE.write_text("\n".join(log_lines))
        log(f"Log gerado em {LOG_FILE}")

    return total_changes

# ── MAIN ─────────────────────────────────────────────────────────────────

def main():
    log("=== Auto Dream Adaptado — Mente Coletiva ===")
    log("Processando: memory-agent + Livy Deep (main)")

    acquire_lock()
    try:
        log("Fase 1: Orientation (todos os espaços)")
        indexes = load_memory_indexes()
        total_referenced = sum(len(v["referenced"]) for v in indexes.values())
        log(f"  Índices lidos, {total_referenced} topic files referenciados")

        log("Fase 2: Gather Signal (todos os espaços)")
        all_signals = gather_signal_all(indexes)
        for space_name, signals in all_signals.items():
            log(f"  [{space_name}]")
            log(f"    relative_dates: {len(signals['relative_dates'])}")
            log(f"    stale: {len(signals['stale'])}")
            log(f"    orphaned: {len(signals['orphaned'])}")
            log(f"    multi_date warnings: {len(signals['multi_date'])}")

        log("Fase 3: Consolidation (DRY RUN)")
        changes = consolidate_all(all_signals, dry_run=True)
        log(f"  {len(changes)} mudanças pendentes")

        log("Fase 4: Prune & Index (DRY RUN)")
        prune_and_index_all(all_signals, changes, dry_run=True)

        if changes:
            log("=== DRY RUN CONCLUÍDO — aplicando ===")
            changes = consolidate_all(all_signals, dry_run=False)
            prune_and_index_all(all_signals, changes, dry_run=False)
        else:
            log("=== Nenhuma mudança necessária ===")

    finally:
        release_lock()

if __name__ == "__main__":
    main()
