# -*- coding: utf-8 -*-
import json
from pathlib import Path

base = Path("scripts/arete/relatorios/g2v/v301_geometry_gate")
d = json.loads((base / "V301_GEOMETRY_GATE.json").read_text(encoding="utf-8"))
print("counts", d["counts"])
for r in d["results"]:
    lab = str(r.get("label") or "")
    if lab in ("V301.A", "V301.B") or (
        lab.startswith("CONT") and r.get("pair_status") == "paired"
    ):
        m = r.get("metrics") or {}
        print("---", lab, "->", r.get("n4_label"), r["verdict"])
        print(" R", m.get("r_match"), "G", m.get("g_match"), "inv", m.get("invented_r"))
        print(" miss", m.get("miss_r"))
        print(" extra", m.get("extra_r"))

for name in ["B_V301.B_n2.json", "B_V301.B_n4.json", "A_V301.A_n2.json", "A_V301.A_n4.json"]:
    p = base / "ledgers" / name
    if not p.exists():
        print("missing", name)
        continue
    ld = json.loads(p.read_text(encoding="utf-8"))
    vals = sorted(c.get("measurement_cm") for c in (ld.get("cotas") or []))
    print(name, vals)
