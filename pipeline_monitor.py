#!/usr/bin/env python3
"""
CAD Pipeline Batch Monitor
Checks every 10 minutes:
- Both python processes alive
- Log growth
- Pavimentos done count
- batch_report.json completion
- Restarts batch/prerender if dead
"""
import subprocess, json, time, os, sys
from pathlib import Path
from datetime import datetime

LOG_FILE   = Path("D:/Agente-cad-PYSIDE/monitor.log")
BATCH_LOG  = Path("D:/Agente-cad-PYSIDE/batch_run_resume.log")
PRE_LOG    = Path("D:/Agente-cad-PYSIDE/nim_prerender.log")
DATA_DIR   = Path("D:/Agente-cad-PYSIDE/DADOS-OBRAS")
PYTHON     = "C:/Python314/python.exe"
COMPLETE   = Path("D:/Agente-cad-PYSIDE/BATCH_COMPLETE.txt")
REPORT     = Path("D:/Agente-cad-PYSIDE/batch_report.json")
LOCK_FILE  = Path(os.environ.get("TEMP", "C:/Users/Thierry/AppData/Local/Temp")) / "pipeline_batch.lock"
INTERVAL   = 600  # 10 minutes

def ts():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def log(msg):
    line = f"[{ts()}] {msg}"
    print(line, flush=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(line + "\n")

def is_batch_alive():
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "CommandLine"],
            capture_output=True, text=True, timeout=15
        )
        return "pipeline_batch" in r.stdout
    except Exception as e:
        log(f"  WARN: wmic check error: {e}")
        return True  # assume alive if can't check

def is_prerender_alive():
    try:
        r = subprocess.run(
            ["wmic", "process", "where", "name='python.exe'", "get", "CommandLine"],
            capture_output=True, text=True, timeout=15
        )
        return "nim_prerender_worker" in r.stdout
    except:
        return True

def count_done():
    done = 0
    done_names = []
    try:
        for obra_dir in DATA_DIR.iterdir():
            rpt = obra_dir / "Fase-8_Revisao_Entrega" / "pipeline_report.json"
            if not rpt.exists():
                continue
            try:
                r = json.loads(rpt.read_bytes().decode("utf-8", "replace"))
                if r.get("pavimento") and r.get("status") not in ["REPROVADO"]:
                    done += 1
                    done_names.append(obra_dir.name)
            except:
                pass
    except Exception as e:
        log(f"  WARN: count_done error: {e}")
    return done, done_names

def count_total():
    disc = DATA_DIR / "dxf_discovery.json"
    if not disc.exists():
        return 92
    try:
        d = json.loads(disc.read_bytes().decode("utf-8"))
        total = 0
        for obra in d.values():
            for pav, tipos in obra.items():
                if tipos.get("PL") and tipos.get("LV") and tipos.get("LJ"):
                    total += 1
        return total
    except:
        return 92

def restart_batch():
    log("  ACTION: Clearing lock file and restarting batch...")
    if LOCK_FILE.exists():
        try:
            LOCK_FILE.unlink()
            log(f"  ACTION: Deleted lock file {LOCK_FILE}")
        except Exception as e:
            log(f"  WARN: Could not delete lock: {e}")
    cmd = (
        'cd /d "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main" && '
        'set PYTHONIOENCODING=utf-8 && set PYTHONUNBUFFERED=1 && '
        '"C:/Python314/python.exe" -u scripts/pipeline_batch.py '
        '--data-dir "D:/Agente-cad-PYSIDE/DADOS-OBRAS" '
        '>> "D:/Agente-cad-PYSIDE/batch_run_resume.log" 2>&1'
    )
    subprocess.Popen(cmd, shell=True)
    log("  ACTION: Batch restart command issued.")

def restart_prerender():
    log("  ACTION: Restarting prerender worker...")
    cmd = (
        'cd /d "D:/Agente-cad-PYSIDE/Agente-cad-PYSIDE-Restored-main" && '
        'set PYTHONIOENCODING=utf-8 && '
        '"C:/Python314/python.exe" -u scripts/nim_prerender_worker.py '
        '--data-dir "D:/Agente-cad-PYSIDE/DADOS-OBRAS" '
        '--out-dir "D:/Agente-cad-PYSIDE/validacao_visual" '
        '--interval 60 '
        '>> "D:/Agente-cad-PYSIDE/nim_prerender.log" 2>&1'
    )
    subprocess.Popen(cmd, shell=True)
    log("  ACTION: Prerender restart command issued.")

def write_complete(done, total, done_names):
    content = "BATCH PIPELINE COMPLETE\n"
    content += "=======================\n"
    content += f"Completed: {ts()}\n"
    content += f"Pavimentos done: {done}/{total}\n\n"
    content += "Completed obras:\n"
    for n in sorted(done_names):
        content += f"  - {n}\n"
    COMPLETE.write_text(content, encoding="utf-8")
    log(f"  SUCCESS: Written BATCH_COMPLETE.txt -- {done}/{total} pavimentos done.")

def check_cycle(prev_log_size, cycle_num):
    log(f"=== CHECK #{cycle_num} ===")

    batch_alive = is_batch_alive()
    pre_alive   = is_prerender_alive()
    log(f"  Processes: batch={'ALIVE' if batch_alive else 'DEAD'}, prerender={'ALIVE' if pre_alive else 'DEAD'}")

    cur_size = BATCH_LOG.stat().st_size if BATCH_LOG.exists() else 0
    growth = cur_size - prev_log_size
    log(f"  Batch log size: {cur_size} bytes (+{growth} since last check)")

    done, done_names = count_done()
    total = count_total()
    log(f"  Progress: {done}/{total} pavimentos DONE")

    try:
        text = BATCH_LOG.read_text(encoding="utf-8", errors="replace")
        conclu = text.count("PIPELINE CONCLU")
        log(f"  'PIPELINE CONCLU' markers in log: {conclu}")
    except:
        pass

    if REPORT.exists():
        try:
            rpt = json.loads(REPORT.read_bytes().decode("utf-8", "replace"))
            log(f"  batch_report.json: total={rpt.get('total')}, done={rpt.get('done')}")
        except:
            log("  batch_report.json exists but could not parse")

    if COMPLETE.exists():
        log("  BATCH_COMPLETE.txt already exists -- pipeline complete!")
        return cur_size, True

    if done >= total and total > 0:
        log(f"  All {total} pavimentos complete -- writing BATCH_COMPLETE.txt")
        write_complete(done, total, done_names)
        return cur_size, True

    if batch_alive and growth == 0 and cycle_num > 1:
        log("  WARN: Batch alive but log not growing -- may be stalled (monitoring)")

    if not batch_alive:
        log("  ALERT: Batch process DEAD -- restarting!")
        restart_batch()

    if not pre_alive:
        log("  ALERT: Prerender process DEAD -- restarting!")
        restart_prerender()

    eta_min = max(0, (total - done) * 10)
    log(f"  ETA estimate: ~{eta_min} min remaining (~{eta_min//60}h {eta_min%60}m)")
    log("")
    return cur_size, False

def main():
    log("=== CAD Pipeline Monitor STARTED ===")
    log(f"Interval: {INTERVAL}s (10 min) | Target: 92 pavimentos")
    log(f"Monitor log: {LOG_FILE}")
    log("")

    prev_size = BATCH_LOG.stat().st_size if BATCH_LOG.exists() else 0
    cycle = 0

    # Run first check immediately
    cycle += 1
    prev_size, done = check_cycle(prev_size, cycle)
    if done:
        log("=== MONITORING COMPLETE ===")
        return

    while True:
        time.sleep(INTERVAL)
        cycle += 1
        prev_size, done = check_cycle(prev_size, cycle)
        if done:
            log("=== MONITORING COMPLETE -- all pavimentos done ===")
            break

if __name__ == "__main__":
    main()
