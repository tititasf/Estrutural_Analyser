#!/usr/bin/env python3
"""Gate visual de prontidão — PIL, LAJ, FV, LV via g2v_harness (backend CLI).

Mesmo contrato para as quatro classes: materializa SVGs+manifesto em paralelo.
Não substitui veredito humano/agente; PASS = evidência visual gerável.

Exemplos:
  python scripts/arete/qa_g2v_visual_gate.py --pav 13_PAV
  python scripts/arete/qa_g2v_visual_gate.py --pav 13_PAV --classe PIL --classe LAJ
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
HARNESS = Path(__file__).resolve().parent / "g2v_harness.py"
CLASSES = ("PIL", "LAJ", "FV", "LV")
DEFAULT_ITEMS = {
    "PIL": ["P1", "P35"],
    "LAJ": ["L318", "L319"],
    "FV": ["V301", "V305", "V312"],
    "LV": ["V301", "V303", "V327"],
}
SCHEMA = "arete.qa_g2v_visual_gate/v2"


def run_harness(*, classe: str, pav: str, items: list[str], par: str) -> dict:
    t0 = time.perf_counter()
    cmd = [
        sys.executable, "-X", "utf8", str(HARNESS),
        "--classe", classe, "--pav", pav, "--backend", "cli", "--par", par,
    ]
    if items:
        cmd.extend(["--item", *items])
    completed = subprocess.run(
        cmd, cwd=str(REPO), capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    stderr = completed.stderr or ""
    env_blocker = None
    if "playwright" in stderr.lower() and "executable doesn't exist" in stderr.lower():
        env_blocker = "playwright_browser_missing"
    return {
        "classe": classe,
        "par": par,
        "items": items,
        "returncode": completed.returncode,
        "stdout_tail": (completed.stdout or "")[-2000:],
        "stderr_tail": stderr[-1000:],
        "ok": completed.returncode == 0,
        "env_blocker": env_blocker,
        "elapsed_ms": int((time.perf_counter() - t0) * 1000),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pav", default="13_PAV")
    parser.add_argument("--par", default="n1xn2", choices=("n1xn2", "n2xn4", "n3xn4"))
    parser.add_argument("--classe", action="append", choices=CLASSES, dest="classes")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--pil-item", action="append", dest="pil_items")
    parser.add_argument("--laj-item", action="append", dest="laj_items")
    parser.add_argument("--fv-item", action="append", dest="fv_items")
    parser.add_argument("--lv-item", action="append", dest="lv_items")
    parser.add_argument("--out", type=Path)
    # compat: --obra ignorado (harness não aceita)
    parser.add_argument("--obra", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args()

    classes = list(args.classes) if args.classes else list(CLASSES)
    items_map = {
        "PIL": args.pil_items or DEFAULT_ITEMS["PIL"],
        "LAJ": args.laj_items or DEFAULT_ITEMS["LAJ"],
        "FV": args.fv_items or DEFAULT_ITEMS["FV"],
        "LV": args.lv_items or DEFAULT_ITEMS["LV"],
    }
    t0 = time.perf_counter()
    results: list[dict] = []
    workers = max(1, min(args.workers, len(classes)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(
                run_harness,
                classe=classe,
                pav=args.pav,
                items=items_map[classe],
                par=args.par,
            ): classe
            for classe in classes
        }
        by_class: dict[str, dict] = {}
        for fut in as_completed(futs):
            by_class[futs[fut]] = fut.result()
        results = [by_class[c] for c in classes]

    blockers = sorted({r.get("env_blocker") for r in results if r.get("env_blocker")})
    report = {
        "schema": SCHEMA,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "pav": args.pav,
        "par": args.par,
        "classes": classes,
        "workers": workers,
        "elapsed_ms_total": int((time.perf_counter() - t0) * 1000),
        "results": results,
        "ok": all(r["ok"] for r in results),
        "env_blockers": blockers,
        "note": (
            "Harness CLI materializa SVGs nas 4 classes; veredito visual humano/agente "
            "ainda obrigatório para selar Arete. PASS = evidência visual gerável. "
            "playwright_browser_missing → `python -m playwright install chromium`."
        ),
    }
    out = args.out or (
        Path(__file__).resolve().parent / "relatorios" / "g2v" /
        f"qa_visual_gate_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "ok": report["ok"],
        "out": str(out),
        "elapsed_ms_total": report["elapsed_ms_total"],
        "results": [
            {
                "classe": r["classe"],
                "ok": r["ok"],
                "returncode": r["returncode"],
                "elapsed_ms": r.get("elapsed_ms"),
                "env_blocker": r.get("env_blocker"),
            }
            for r in results
        ],
    }, ensure_ascii=False, indent=2))
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
