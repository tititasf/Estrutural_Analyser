# -*- coding: utf-8 -*-
"""Dump de TODAS as linhas do N4 VIEW_B.dxf na banda de uma unidade."""
import json
import sys
from pathlib import Path

import ezdxf

GATE = Path(r"D:\Agente-cad-PYSIDE\Agente-cad-PYSIDE-Restored-main\scripts\arete\relatorios\g2v\v301_geometry_gate")
N4 = Path(r"D:\Agente-cad-PYSIDE\DADOS-OBRAS\Obra_TREINO_1\Fase-6_Execucao_CAD\n4\LV_preview_V301_A.dxf")

unit = sys.argv[1] if len(sys.argv) > 1 else "V301.B"
led = json.loads((GATE / "ledgers" / f"B_{unit}_n4.json").read_text(encoding="utf-8"))
ox, oy = led["origin_abs"]
h_body = led["h_body"]
total_w = led["total_w"]
print(f"unit={unit} origin=({ox:.1f},{oy:.1f}) h_body={h_body} total_w={total_w} laje estimada acima de y={oy + h_body:.1f}")

doc = ezdxf.readfile(str(N4))
msp = doc.modelspace()

x0, x1 = ox - 30, ox + total_w + 60
y0, y1 = oy - 60, oy + h_body + 60

rows = []


def _emit(sx, sy, tx, ty, layer):
    mxx = (sx + tx) / 2
    myy = (sy + ty) / 2
    if not (x0 <= mxx <= x1 and y0 <= myy <= y1):
        return
    dx = "V" if abs(sx - tx) < 0.4 else ("H" if abs(sy - ty) < 0.4 else "D")
    rows.append((
        dx,
        round(sx - ox, 1), round(sy - oy, 1),
        round(tx - ox, 1), round(ty - oy, 1),
        layer,
    ))


for e in msp:
    t = e.dxftype()
    if t == "LINE":
        _emit(e.dxf.start.x, e.dxf.start.y, e.dxf.end.x, e.dxf.end.y, e.dxf.layer)
    elif t == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        if e.closed:
            pts.append(pts[0])
        for (ax, ay), (bx, by) in zip(pts, pts[1:]):
            _emit(ax, ay, bx, by, e.dxf.layer)

rows.sort(key=lambda r: (r[0], r[5], r[1], r[2]))
print(f"{len(rows)} linhas na banda (coords relativas a origem):")
for r in rows:
    print(f"  {r[0]} ({r[1]:7.1f},{r[2]:6.1f})->({r[3]:7.1f},{r[4]:6.1f})  {r[5]}")
