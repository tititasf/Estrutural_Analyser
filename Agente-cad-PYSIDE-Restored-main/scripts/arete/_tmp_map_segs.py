# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path(__file__).resolve().parent / "relatorios/g2v/v301_geometry_gate/V301_GEOMETRY_GATE.json"
data = json.loads(p.read_text(encoding="utf-8"))
results = list(data.get("results") or [])
print("ALL RESULTS")
for j, r in enumerate(results):
    print(
        f"  results[{j:02d}] side={r.get('side')} lab={r.get('label')!s:16} "
        f"n4={r.get('n4_label')!s:16} pair={r.get('pair_status')} {r.get('verdict')}"
    )

paired = [
    (j, r) for j, r in enumerate(results)
    if str(r.get("side") or "").upper() in {"A", "B"}
    and str(r.get("pair_status") or "") == "paired"
]


def sort_key(item):
    r = item[1]
    lab = str(r.get("label") or "")
    side = str(r.get("side") or "")
    primary = 0 if lab in ("V301.A", "V301.B") else (1 if "CONT" in lab else 2)
    return (side, primary, lab, item[0])


ordered = sorted(paired, key=sort_key)
seg = {"A": 0, "B": 0}
print("\nHTML CARDS")
for orig_i, r in ordered:
    side = str(r.get("side") or "").upper()
    seg[side] += 1
    name = f"SEGMENTO {seg[side]}{side}"
    print(
        f"{name:16} results_i={orig_i:02d} preview=seg_{orig_i:02d} "
        f"lab={r.get('label')!s:16} n4={r.get('n4_label')!s:16}"
    )
