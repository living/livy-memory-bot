#!/usr/bin/env python3
"""
Dream Consolidation — memory-agent sonha e consolida TODAS as memórias.

Este script é o "sonho" do memory-agent — ele processa:
1. Própria memória: ~/.openclaw/workspace-livy-memory/memory/
2. Memória do main: ~/.openclaw/workspace/memory/

Isso permite que o memory-agent curie e consolide todas as memórias
da Living Consultoria num único lugar.
"""

import json, os, re, sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
# Memória do memory-agent
MEMORY_AGENT_MEMORY = Path("/home/lincoln/.openclaw/workspace-livy-memory/memory")
MEMORY_AGENT_INDEX = Path("/home/lincoln/.openclaw/workspace-livy-memory/MEMORY.md")

# Memória do main (Livy Deep)
MAIN_MEMORY = Path("/home/lincoln/.openclaw/workspace/memory")
MAIN_INDEX = Path("/home/lincoln/.openclaw/workspace/MEMORY.md")

# Sessions do main
MAIN_SESSIONS = Path("/home/lincoln/.openclaw/agents/main/sessions")

LOOKBACK_DAYS = 1

def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}", flush=True)

# ── Helpers ────────────────────────────────────────────────────────────────────

def read_file(path):
    try:
        return path.read_text()
    except:
        return ""

def list_daily_logs(memory_dir):
    """Lista logs diários (YYYY-MM-DD*.md)."""
    if not memory_dir.exists():
        return []
    return sorted([f for f in memory_dir.glob("*.md") if f.match("????-??-??*.md")])

def list_topic_files(memory_dir):
    """Lista topic files (não daily logs)."""
    daily_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}")
    if not memory_dir.exists():
        return []
    return [f for f in memory_dir.glob("*.md")
            if not daily_pattern.match(f.name) and f.name not in ("heartbeat-state.json", "consolidation-log.md", ".consolidation.lock")]

def get_recent_sessions(sessions_dir, days=1):
    """Retorna session files dos últimos N dias."""
    if not sessions_dir.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    result = []
    for f in sorted(sessions_dir.glob("*.jsonl")):
        try:
            timestamps = []
            for line in f.open():
                if '"timestamp"' in line:
                    try:
                        ts = line.strip().split('"timestamp":"')[1].split('"')[0]
                        timestamps.append(datetime.fromisoformat(ts))
                    except:
                        pass
            if timestamps and max(timestamps) > cutoff:
                result.append(f)
        except:
            pass
    return sorted(result, key=lambda x: x.stat().st_mtime, reverse=True)[:5]

def extract_signal(path, max_lines=200):
    """Extrai mensagens de uma session JSONL."""
    entries = []
    try:
        with open(path) as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    break
                try:
                    entry = json.loads(line)
                    if entry.get("type") == "message":
                        content = entry.get("message", {}).get("content", [])
                        if isinstance(content, list):
                            texts = [p["text"][:300] for p in content
                                     if isinstance(p, dict) and p.get("type") == "text" and p.get("text")]
                            if texts:
                                role = entry.get("message", {}).get("role", "?")
                                entries.append(f"[{role}] {' '.join(texts)}")
                except:
                    pass
    except:
        pass
    return "\n".join(entries[-50:])

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    log("=== Dream Consolidation — memory-agent ===")

    all_signal = {
        "daily_logs": [],
        "topic_files": [],
        "sessions": [],
    }

    # 1. Processa memória do memory-agent
    log(f"Processando memória do memory-agent: {MEMORY_AGENT_MEMORY}")
    for f in list_daily_logs(MEMORY_AGENT_MEMORY):
        all_signal["daily_logs"].append(("memory-agent", f.name, read_file(f)))
    for f in list_topic_files(MEMORY_AGENT_MEMORY):
        all_signal["topic_files"].append(("memory-agent", f.name, read_file(f)))

    # 2. Processa memória do main (Livy Deep)
    log(f"Processando memória do main: {MAIN_MEMORY}")
    for f in list_daily_logs(MAIN_MEMORY):
        all_signal["daily_logs"].append(("main", f.name, read_file(f)))
    for f in list_topic_files(MAIN_MEMORY):
        all_signal["topic_files"].append(("main", f.name, read_file(f)))

    # 3. Sessions do main
    log(f"Processando sessões do main: {MAIN_SESSIONS}")
    for sess in get_recent_sessions(MAIN_SESSIONS, LOOKBACK_DAYS):
        content = extract_signal(sess)
        if content:
            all_signal["sessions"].append(("main", sess.name, content))

    # Summary
    log(f"📊 Resumo:")
    log(f"  - Daily logs: {len(all_signal['daily_logs'])}")
    log(f"  - Topic files: {len(all_signal['topic_files'])}")
    log(f"  - Sessions: {len(all_signal['sessions'])}")

    # Aqui seria a fase de análise e consolidação
    # Por ora, apenas reportamos o que encontramos

    # Salva signal para análise
    signal_file = MEMORY_AGENT_MEMORY / "dream-signal.json"
    with open(signal_file, "w") as f:
        json.dump(all_signal, f, indent=2, default=str)
    log(f"Signal salvo em: {signal_file}")

    log("=== Dream Consolidation COMPLETE ===")
    return all_signal

if __name__ == "__main__":
    main()
