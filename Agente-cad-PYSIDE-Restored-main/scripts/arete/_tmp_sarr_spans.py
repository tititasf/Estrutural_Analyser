# -*- coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from arete.gerar_lv_n4_fichas import _entry_from_live_recorte
from lv_n4_face_unit_selection import select_n4_face_units
import gerar_lv_dxf_stog as lv

e = _entry_from_live_recorte("V301")
fus = select_n4_face_units(lv, e.get("face_units") or [], "V301")
for i, u in enumerate(fus):
    side = str(u.get("side") or "").upper()
    if side != "B":
        continue
    lab = str(u.get("label") or "?")
    h = float(u.get("h_body") or u.get("h") or 0)
    hs = u.get("sarrafos_horizontais") or []
    if not hs:
        continue
    print(f"\n==== {i} {lab} h={h} n={len(hs)}")
    for s in hs:
        y = round(float(s.get("y_offset", 0) or 0), 1)
        x1 = round(float(s.get("x_left", 0) or 0), 1)
        x2 = round(float(s.get("x_right", 0) or 0), 1)
        mark = " ABOVE" if y > h + 1 else ""
        print(f"  y={y:6.1f} x={x1:6.1f}->{x2:6.1f}{mark}")
