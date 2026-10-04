# -*- coding: utf-8 -*-
"""Diff linhas must_reproduce N2 x N4 — UNIT.B#8 (11B) e UNIT.B#11 (6B)."""
import json
from pathlib import Path

BASE = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\relatorios\g2v\v301_geometry_gate\ledgers")


def load(unit, tag):
    return json.loads((BASE / f"B_{unit}_{tag}.json").read_text(encoding="utf-8"))


def key(L):
    r = L["rel"]
    return (L["layer"], L["orient"], round(r["x1"], 1), round(r["y1"], 1),
            round(r["x2"], 1), round(r["y2"], 1))


def sig(L):
    r = L["rel"]
    return (f"{L['layer'][:9]:9} {L['orient']} "
            f"({r['x1']:7.1f},{r['y1']:6.1f})->({r['x2']:7.1f},{r['y2']:6.1f}) "
            f"len={L['length_cm']:6.1f}")


def near(a, b, tol=2.5):
    if a[0] != b[0] or a[1] != b[1]:
        return False
    return all(abs(x - y) <= tol for x, y in zip(a[2:], b[2:]))


for unit in ("UNIT.B_8", "UNIT.B_11", "UNIT.B_7"):
    n2, n4 = load(unit, "n2"), load(unit, "n4")
    g2 = [L for L in n2["lines"] if "must_reproduce" in (L.get("flags") or [])]
    g4 = [L for L in n4["lines"] if "must_reproduce" in (L.get("flags") or [])]
    k4 = [key(L) for L in g4]
    k2 = [key(L) for L in g2]
    miss = [L for L in g2 if not any(near(key(L), b) for b in k4)]
    extra = [L for L in g4 if not any(near(key(L), a) for a in k2)]
    print(f"\n######## {unit}  N2 must={len(g2)} N4 must={len(g4)}  miss={len(miss)} extra={len(extra)}")
    print("--- MISSING no N4 (N2 tem, N4 nao):")
    for L in sorted(miss, key=lambda l: (l["layer"], l["rel"]["y1"], l["rel"]["x1"])):
        print("  ", sig(L))
    print("--- EXTRA no N4 (N4 tem, N2 nao):")
    for L in sorted(extra, key=lambda l: (l["layer"], l["rel"]["y1"], l["rel"]["x1"])):
        print("  ", sig(L))
