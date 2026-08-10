# -*- coding: utf-8 -*-
"""Gate de fidelidade N2×N4 — camadas G (geometria) e R (rótulos).

Uso (V301 face A como âncora do protocolo):
  py -3 scripts/arete/gate_n2_n4_fidelidade.py \\
      --n2 path/LV_V301_motor_....dxf \\
      --n4 path/n4/LV_preview_V301_VIEW_A.dxf \\
      --trace scripts/arete/relatorios/g2v/v301_n2_inventory/trace_n2_n4_faceA.json

Ou só a partir do trace já gerado por ``_v301_n2_inventory.py``:

  py -3 scripts/arete/gate_n2_n4_fidelidade.py --trace .../trace_n2_n4_faceA.json

Exit code 0 = PASS inventário; 1 = FAIL; 2 = uso/erro.

Ver: docs/QA-N2-N4-COMPARACAO-FIDELIDADE.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


def _norm_val(s) -> str | None:
    if s is None:
        return None
    t = str(s).strip().replace(",", ".")
    if not re.fullmatch(r"-?\d+(\.\d+)?", t):
        return None
    v = float(t)
    if abs(v - round(v)) < 0.05:
        return str(int(round(v)))
    # 1 casa, sem zeros inúteis
    t1 = f"{v:.1f}"
    if t1.endswith(".0"):
        return t1[:-2]
    return t1.rstrip("0").rstrip(".") if "." in t1 else t1


def gate_from_trace(trace: dict) -> dict:
    """Aplica regras hard-fail no trace do inventário completo."""
    summary = trace.get("summary") or {}
    cotas = trace.get("cotas") or []
    lines = trace.get("lines") or []
    extra_c = list(trace.get("cotas_extra_n4") or [])
    extra_l = list(trace.get("lines_extra_n4") or [])

    missing_own = [
        c
        for c in cotas
        if c.get("status") == "MISSING_N4"
    ]
    near_wrong = [
        c
        for c in cotas
        if c.get("status") in ("NEAR_VALUE",)
        and abs(float(c.get("measurement_cm") or 0) - float((c.get("n4") or {}).get("measurement_cm") or 0))
        >= 0.15
    ]

    # EXTRA estrutural (Painéis/SARR) — ticks não vêm como EXTRA do N4 em geral
    extra_struct = [
        e
        for e in extra_l
        if e.get("family") in ("Painéis", "SARR", "Paineis")
    ]

    fails = []
    if extra_c:
        fails.append(
            {
                "code": "COTA_EXTRA_N4",
                "detail": [
                    {
                        "measurement_cm": e.get("measurement_cm"),
                        "pos": e.get("pos"),
                    }
                    for e in extra_c
                ],
            }
        )
    if missing_own:
        fails.append(
            {
                "code": "COTA_MISSING_OWN_FACE",
                "detail": [
                    {
                        "content": c.get("content"),
                        "measurement_cm": c.get("measurement_cm"),
                        "insert_rel": c.get("insert_rel"),
                    }
                    for c in missing_own
                ],
            }
        )
    if near_wrong:
        fails.append(
            {
                "code": "COTA_NEAR_VALUE_SUSPEITO",
                "detail": [
                    {
                        "content": c.get("content"),
                        "n2": c.get("measurement_cm"),
                        "n4": (c.get("n4") or {}).get("measurement_cm"),
                    }
                    for c in near_wrong
                ],
            }
        )
    if extra_struct:
        fails.append(
            {
                "code": "LINE_EXTRA_N4_STRUCT",
                "detail": extra_struct,
            }
        )

    cota_status = Counter(c.get("status") for c in cotas)
    line_status = Counter(L.get("status") for L in lines)

    return {
        "verdict": "PASS" if not fails else "FAIL",
        "fails": fails,
        "counts": {
            "cotas": dict(cota_status),
            "lines": dict(line_status),
            "cotas_extra_n4": len(extra_c),
            "lines_extra_n4": len(extra_l),
            "missing_cotas_own": len(missing_own),
        },
        "protocol": "QA-N2-N4-COMPARACAO-FIDELIDADE",
        "rule": "R_N4 ⊆ R_N2_own_face; EXTRA estrutural = FAIL",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trace", type=Path, required=True, help="trace_n2_n4_*.json")
    ap.add_argument("--json-out", type=Path, default=None)
    args = ap.parse_args(argv)

    if not args.trace.exists():
        print(f"[ERRO] trace não encontrado: {args.trace}", file=sys.stderr)
        return 2

    trace = json.loads(args.trace.read_text(encoding="utf-8"))
    report = gate_from_trace(trace)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(text, encoding="utf-8")

    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
